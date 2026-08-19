using System;
using A3GameRuntime;
using UnityEngine;

namespace ArenaFighterExample
{
    /// <summary>
    /// Orchestrates an arena fight: spawns the player and AI opponent,
    /// wires up references, and tracks win/loss state. Integrates with the
    /// A3GameRuntime subsystem when present for entity identity tracking.
    /// </summary>
    [AddComponentMenu("3AGameFactory/Arena Fighter GameMode")]
    public class ArenaFighterGameMode : MonoBehaviour, IA3GameEntityFactory
    {
        [Header("Spawn Points")]
        [SerializeField] private Transform playerSpawn;
        [SerializeField] private Transform opponentSpawn;

        [Header("Prefabs (optional)")]
        [SerializeField] private GameObject playerPrefab;
        [SerializeField] private GameObject opponentPrefab;

        [Header("Input")]
        [SerializeField] private bool localInputEnabled = true;

        private A3GameRuntimeSubsystem _registeredRuntime;
        private string _runtimePlayerEntityId = string.Empty;

        /// <summary>Runtime player fighter (set after Setup).</summary>
        public ArenaFighterController Player { get; private set; }

        /// <summary>Runtime AI opponent fighter (set after Setup).</summary>
        public ArenaFighterController Opponent { get; private set; }

        /// <summary>Whether the round is currently active.</summary>
        public bool IsRoundActive { get; private set; }

        /// <summary>Whether the player has won the current round.</summary>
        public bool PlayerWon { get; private set; }

        public bool IsReady { get; private set; }
        public bool LocalInputEnabled
        {
            get => localInputEnabled;
            set => localInputEnabled = value;
        }
        public float PlayerHealth => Player != null ? Player.Health : 0f;
        public float OpponentHealth => Opponent != null ? Opponent.Health : 0f;

        public event Action OnRoundStarted;
        public event Action OnPlayerWon;
        public event Action OnPlayerLost;
        public event Action<bool> OnPlayerAttack;
        public event Action OnStateChanged;

        void Awake()
        {
            SetupArena();
        }

        void Start()
        {
            Setup();
        }

        /// <summary>
        /// Ensure spawn points exist. Called from Awake() in normal play,
        /// but can also be called explicitly before Setup() in batchmode.
        /// </summary>
        public void SetupArena()
        {
            EnsureSpawnPoint(ref playerSpawn, "PlayerSpawn", new Vector3(-3f, 0f, 0f));
            EnsureSpawnPoint(ref opponentSpawn, "OpponentSpawn", new Vector3(3f, 0f, 0f));
        }

        private void EnsureSpawnPoint(ref Transform spawn, string name, Vector3 pos)
        {
            if (spawn != null)
                return;
            var go = new GameObject(name);
            go.transform.SetParent(transform);
            go.transform.position = pos;
            spawn = go.transform;
        }

        /// <summary>
        /// Spawn the player and opponent fighters, wire up the AI, and
        /// start the round.
        /// </summary>
        public void Setup()
        {
            if (IsReady)
                return;

            SetupArena();
            Player = SpawnFighter("Player", playerSpawn.position, playerPrefab);
            Opponent = SpawnFighter("Opponent", opponentSpawn.position, opponentPrefab);

            var ai = Opponent.GetComponent<ArenaFighterAI>();
            if (ai == null)
                ai = Opponent.gameObject.AddComponent<ArenaFighterAI>();
            ai.Self = Opponent;
            ai.Player = Player;

            Player.StateChanged += PublishState;
            Player.PrimaryActionRequested += HandlePrimaryActionRequested;
            Player.Died += HandlePlayerDied;
            Opponent.StateChanged += PublishState;
            Opponent.Died += HandleOpponentDied;

            IsRoundActive = true;
            PlayerWon = false;
            IsReady = true;
            TryRegisterRuntimeFactory();
            OnRoundStarted?.Invoke();
            PublishState();
        }

        private ArenaFighterController SpawnFighter(
            string name, Vector3 position, GameObject prefab)
        {
            GameObject obj;
            if (prefab != null)
                obj = Instantiate(prefab, position, Quaternion.identity);
            else
                obj = new GameObject(name);

            obj.name = name;
            obj.transform.SetParent(transform, true);
            obj.transform.position = position;

            var fighter = obj.GetComponent<ArenaFighterController>();
            if (fighter == null)
                fighter = obj.AddComponent<ArenaFighterController>();

            AttachRuntimeMetadata(fighter);
            return fighter;
        }

        private static void AttachRuntimeMetadata(ArenaFighterController fighter)
        {
            var runtime = A3GameRuntimeSubsystem.Instance;
            string id = A3GameRuntimeSubsystem.NewId("fighter");
            fighter.entityId = id;

            var entity = fighter.GetComponent<A3GameRuntimeEntityComponent>();
            if (entity == null)
                entity = fighter.gameObject.AddComponent<A3GameRuntimeEntityComponent>();
            entity.Initialize(id, runtime != null ? runtime.worldId : "arena_fighter");
        }

        void Update()
        {
            TryRegisterRuntimeFactory();
            if (!IsReady)
                return;

            if (!IsRoundActive)
            {
                if (Input.GetKeyDown(KeyCode.Return) ||
                    Input.GetKeyDown(KeyCode.KeypadEnter))
                    RestartRound();
                return;
            }

            if (localInputEnabled)
            {
                float yaw = Player.transform.eulerAngles.y +
                    Input.GetAxis("Mouse X") * 2f;
                Player.ApplyInput(new A3GameRuntimeInputState
                {
                    move_x = Input.GetAxisRaw("Horizontal"),
                    move_y = Input.GetAxisRaw("Vertical"),
                    run = Input.GetKey(KeyCode.LeftShift),
                    yaw = yaw,
                });
                if (Input.GetMouseButtonDown(0) || Input.GetKeyDown(KeyCode.Space))
                    PlayerAttack();
            }
        }

        private void HandlePrimaryActionRequested()
        {
            PlayerAttack();
        }

        public bool PlayerAttack()
        {
            bool connected = IsRoundActive && Player != null &&
                Opponent != null && Player.Attack(Opponent);
            OnPlayerAttack?.Invoke(connected);
            return connected;
        }

        public GameObject CreateEntity(A3GameEntitySpawnRequest request)
        {
            if (!IsReady || Player == null)
                return null;
            if (!string.IsNullOrEmpty(_runtimePlayerEntityId) &&
                _runtimePlayerEntityId != request.entity_id)
                return null;

            _runtimePlayerEntityId = request.entity_id;
            Player.entityId = request.entity_id;
            localInputEnabled = false;
            return Player.gameObject;
        }

        public bool DestroyEntity(string entityId)
        {
            if (string.IsNullOrEmpty(_runtimePlayerEntityId) ||
                entityId != _runtimePlayerEntityId)
                return false;

            _runtimePlayerEntityId = string.Empty;
            localInputEnabled = true;
            if (Player != null)
                Player.ResetEntity();
            return true;
        }

        private void TryRegisterRuntimeFactory()
        {
            var runtime = A3GameRuntimeSubsystem.Instance;
            if (runtime == null || runtime == _registeredRuntime)
                return;
            if (_registeredRuntime != null)
                _registeredRuntime.UnregisterFactory(this);
            runtime.RegisterFactory(this);
            _registeredRuntime = runtime;
        }

        private void HandleOpponentDied()
        {
            if (!IsRoundActive)
                return;
            IsRoundActive = false;
            PlayerWon = true;
            OnPlayerWon?.Invoke();
        }

        private void HandlePlayerDied()
        {
            if (!IsRoundActive)
                return;
            IsRoundActive = false;
            PlayerWon = false;
            OnPlayerLost?.Invoke();
        }

        /// <summary>Restart the round by resetting both fighters.</summary>
        public void RestartRound()
        {
            if (!IsReady)
            {
                Setup();
                return;
            }

            if (Player != null)
            {
                Player.ResetEntity();
            }
            if (Opponent != null)
            {
                Opponent.ResetEntity();
                var ai = Opponent.GetComponent<ArenaFighterAI>();
                if (ai != null)
                    ai.ResetAI();
            }
            IsRoundActive = true;
            PlayerWon = false;
            OnRoundStarted?.Invoke();
            PublishState();
        }

        void OnDestroy()
        {
            if (_registeredRuntime != null)
                _registeredRuntime.UnregisterFactory(this);
            if (Player != null)
            {
                Player.StateChanged -= PublishState;
                Player.PrimaryActionRequested -= HandlePrimaryActionRequested;
                Player.Died -= HandlePlayerDied;
            }
            if (Opponent != null)
            {
                Opponent.StateChanged -= PublishState;
                Opponent.Died -= HandleOpponentDied;
            }
        }

        private void PublishState()
        {
            OnStateChanged?.Invoke();
            Debug.Log(
                "[ARENA_STATE] player_health=" + PlayerHealth.ToString("F1") +
                " opponent_health=" + OpponentHealth.ToString("F1") +
                " active=" + IsRoundActive +
                " player_won=" + PlayerWon);
        }
    }
}
