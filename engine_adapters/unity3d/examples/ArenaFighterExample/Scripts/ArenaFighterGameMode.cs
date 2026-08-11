using A3GameRuntime;
using UnityEngine;

namespace ArenaFighterExample
{
    /// <summary>
    /// Orchestrates an arena fight: spawns the player and AI opponent,
    /// wires up references, and tracks win/loss state. Integrates with the
    /// A3GameRuntime subsystem when present for entity identity tracking.
    /// </summary>
    [AddComponentMenu("AAAGameForge/Arena Fighter GameMode")]
    public class ArenaFighterGameMode : MonoBehaviour
    {
        [Header("Spawn Points")]
        [SerializeField] private Transform playerSpawn;
        [SerializeField] private Transform opponentSpawn;

        [Header("Prefabs (optional)")]
        [SerializeField] private GameObject playerPrefab;
        [SerializeField] private GameObject opponentPrefab;

        /// <summary>Runtime player fighter (set after Setup).</summary>
        public ArenaFighterController Player { get; private set; }

        /// <summary>Runtime AI opponent fighter (set after Setup).</summary>
        public ArenaFighterController Opponent { get; private set; }

        /// <summary>Whether the round is currently active.</summary>
        public bool IsRoundActive { get; private set; }

        /// <summary>Whether the player has won the current round.</summary>
        public bool PlayerWon { get; private set; }

        void Awake()
        {
            EnsureSpawnPoint(ref playerSpawn, "PlayerSpawn", new Vector3(-3f, 0f, 0f));
            EnsureSpawnPoint(ref opponentSpawn, "OpponentSpawn", new Vector3(3f, 0f, 0f));
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
            Player = SpawnFighter("Player", playerSpawn.position, playerPrefab);
            Opponent = SpawnFighter("Opponent", opponentSpawn.position, opponentPrefab);

            var ai = Opponent.gameObject.AddComponent<ArenaFighterAI>();
            ai.Self = Opponent;
            ai.Player = Player;

            IsRoundActive = true;
            PlayerWon = false;
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
            obj.transform.position = position;

            var fighter = obj.GetComponent<ArenaFighterController>();
            if (fighter == null)
                fighter = obj.AddComponent<ArenaFighterController>();

            TryRegisterWithRuntime(fighter, name);
            return fighter;
        }

        private void TryRegisterWithRuntime(ArenaFighterController fighter, string label)
        {
            var runtime = A3GameRuntimeSubsystem.Instance;
            if (runtime == null)
                return;

            string id = A3GameRuntimeSubsystem.NewId("fighter");
            fighter.entityId = id;

            // Attach the runtime entity component so the fighter is observable
            // through the A3GameRuntime session/snapshot pipeline.
            var entity = fighter.GetComponent<A3GameRuntimeEntityComponent>();
            if (entity == null)
                entity = fighter.gameObject.AddComponent<A3GameRuntimeEntityComponent>();
            entity.Initialize(id, runtime.worldId);
        }

        void Update()
        {
            if (!IsRoundActive)
                return;

            if (Opponent != null && Opponent.IsDead)
            {
                IsRoundActive = false;
                PlayerWon = true;
            }
            else if (Player != null && Player.IsDead)
            {
                IsRoundActive = false;
                PlayerWon = false;
            }
        }

        /// <summary>Restart the round by resetting both fighters.</summary>
        public void RestartRound()
        {
            if (Player != null)
            {
                Player.ResetFighter();
                Player.transform.position = playerSpawn.position;
            }
            if (Opponent != null)
            {
                Opponent.ResetFighter();
                Opponent.transform.position = opponentSpawn.position;
                var ai = Opponent.GetComponent<ArenaFighterAI>();
                if (ai != null)
                    ai.ResetAI();
            }
            IsRoundActive = true;
            PlayerWon = false;
        }
    }
}
