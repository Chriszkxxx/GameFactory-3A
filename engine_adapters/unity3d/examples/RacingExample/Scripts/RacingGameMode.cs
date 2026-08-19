using System;
using System.Collections.Generic;
using A3GameRuntime;
using UnityEngine;

namespace RacingExample
{
    /// <summary>
    /// Sets up a racing encounter: spawns the vehicle, configures the lap
    /// counter and checkpoints, and tracks race completion. Integrates with
    /// the A3GameRuntime subsystem for entity identity tracking.
    /// </summary>
    [AddComponentMenu("3AGameFactory/Racing GameMode")]
    public class RacingGameMode : MonoBehaviour, IA3GameEntityFactory
    {
        [Header("Configuration")]
        [SerializeField] private int totalLaps = 3;
        [SerializeField] private int totalCheckpoints = 3;

        [Header("Spawn")]
        [SerializeField] private Transform vehicleSpawn;
        [SerializeField] private GameObject vehiclePrefab;

        [Header("References")]
        [SerializeField] private RacingLapCounter lapCounter;
        [SerializeField] private RacingCheckpoint[] checkpoints;

        [Header("Input")]
        [SerializeField] private bool localInputEnabled = true;

        private A3GameRuntimeSubsystem _registeredRuntime;
        private string _runtimeVehicleEntityId = string.Empty;

        /// <summary>Runtime vehicle controller.</summary>
        public RacingVehicleController Vehicle { get; private set; }

        /// <summary>Whether the race is active.</summary>
        public bool IsRaceActive { get; private set; }

        /// <summary>Whether the race is finished.</summary>
        public bool IsFinished { get; private set; }

        public bool IsReady { get; private set; }
        public bool LocalInputEnabled
        {
            get => localInputEnabled;
            set => localInputEnabled = value;
        }
        public float VehicleSpeed => Vehicle != null ? Vehicle.Speed : 0f;
        public int CurrentLap => lapCounter != null ? lapCounter.CurrentLap : 1;
        public int CheckpointsPassed =>
            lapCounter != null ? lapCounter.CheckpointsPassed : 0;
        public int TotalCheckpoints => totalCheckpoints;

        public event Action OnRaceStarted;
        public event Action OnCheckpointPassed;
        public event Action OnLapCompleted;
        public event Action OnRaceFinished;
        public event Action OnStateChanged;

        /// <summary>Target number of laps.</summary>
        public int TotalLaps => totalLaps;

        /// <summary>The lap counter used by this GameMode.</summary>
        public RacingLapCounter LapCounter => lapCounter;

        void Awake()
        {
            EnsureSceneReferences();
        }

        void Start()
        {
            Setup();
        }

        private void EnsureSceneReferences()
        {
            if (vehicleSpawn == null)
            {
                var go = new GameObject("VehicleSpawn");
                go.transform.SetParent(transform);
                go.transform.position = Vector3.zero;
                vehicleSpawn = go.transform;
            }

            if (lapCounter == null)
            {
                var go = new GameObject("LapCounter");
                go.transform.SetParent(transform);
                lapCounter = go.AddComponent<RacingLapCounter>();
            }

            lapCounter.Configure(totalCheckpoints, 1);
        }

        /// <summary>Set up the vehicle, checkpoints, and start the race.</summary>
        public void Setup()
        {
            if (IsReady)
                return;

            EnsureSceneReferences();
            SpawnVehicle();
            ConfigureCheckpoints();
            lapCounter.OnCheckpointPassed += HandleCheckpointPassed;
            lapCounter.OnLapCompleted += HandleLapCompleted;
            lapCounter.OnStateChanged += PublishState;
            IsRaceActive = true;
            IsFinished = false;
            IsReady = true;
            TryRegisterRuntimeFactory();
            OnRaceStarted?.Invoke();
            PublishState();
        }

        private void SpawnVehicle()
        {
            GameObject obj;
            if (vehiclePrefab != null)
                obj = Instantiate(vehiclePrefab, vehicleSpawn.position, vehicleSpawn.rotation);
            else
                obj = new GameObject("Racing_Vehicle");

            obj.transform.position = vehicleSpawn.position;
            obj.transform.rotation = vehicleSpawn.rotation;
            obj.transform.SetParent(transform, true);

            Vehicle = obj.GetComponent<RacingVehicleController>();
            if (Vehicle == null)
                Vehicle = obj.AddComponent<RacingVehicleController>();

            Vehicle.LapCounter = lapCounter;

            AttachRuntimeMetadata(Vehicle);
        }

        private void ConfigureCheckpoints()
        {
            if (checkpoints == null || checkpoints.Length == 0)
            {
                // Auto-discover checkpoints in children.
                var list = new List<RacingCheckpoint>();
                GetComponentsInChildren(list);
                checkpoints = list.ToArray();
            }

            for (int i = 0; i < checkpoints.Length; i++)
            {
                if (checkpoints[i] == null)
                    continue;

                checkpoints[i].CheckpointIndex = i;
                if (checkpoints[i].LapCounter == null)
                    checkpoints[i].LapCounter = lapCounter;
            }
        }

        private static void AttachRuntimeMetadata(RacingVehicleController vehicle)
        {
            var runtime = A3GameRuntimeSubsystem.Instance;
            string worldId = runtime != null ? runtime.worldId : "racing";
            string id = A3GameRuntimeSubsystem.NewId("vehicle");
            vehicle.entityId = id;

            var entity = vehicle.GetComponent<A3GameRuntimeEntityComponent>();
            if (entity == null)
                entity = vehicle.gameObject.AddComponent<A3GameRuntimeEntityComponent>();
            entity.Initialize(id, worldId);
        }

        void Update()
        {
            TryRegisterRuntimeFactory();
            if (!IsReady)
                return;

            if (!IsRaceActive)
            {
                if (Input.GetKeyDown(KeyCode.Return) ||
                    Input.GetKeyDown(KeyCode.KeypadEnter))
                    Restart();
                return;
            }

            if (localInputEnabled)
            {
                Vehicle.Drive(
                    Input.GetAxisRaw("Vertical"),
                    Input.GetAxisRaw("Horizontal"),
                    Input.GetKey(KeyCode.LeftShift),
                    Time.deltaTime);
            }
        }

        /// <summary>Restart the race from the spawn point.</summary>
        public void Restart()
        {
            if (!IsReady)
            {
                Setup();
                return;
            }

            if (Vehicle != null)
                Vehicle.ResetEntity();

            IsRaceActive = true;
            IsFinished = false;
            lapCounter.ResetCounter();
            OnRaceStarted?.Invoke();
            PublishState();
        }

        public GameObject CreateEntity(A3GameEntitySpawnRequest request)
        {
            if (!IsReady || Vehicle == null)
                return null;
            if (!string.IsNullOrEmpty(_runtimeVehicleEntityId) &&
                _runtimeVehicleEntityId != request.entity_id)
                return null;

            _runtimeVehicleEntityId = request.entity_id;
            Vehicle.entityId = request.entity_id;
            localInputEnabled = false;
            return Vehicle.gameObject;
        }

        public bool DestroyEntity(string entityId)
        {
            if (string.IsNullOrEmpty(_runtimeVehicleEntityId) ||
                entityId != _runtimeVehicleEntityId)
                return false;

            _runtimeVehicleEntityId = string.Empty;
            localInputEnabled = true;
            if (Vehicle != null)
                Vehicle.ResetEntity();
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

        public void Drive(
            float throttle,
            float steering,
            bool boost,
            float deltaTime)
        {
            if (!IsReady || !IsRaceActive)
                return;
            Vehicle.Drive(throttle, steering, boost, deltaTime);
            PublishState();
        }

        private void HandleLapCompleted()
        {
            OnLapCompleted?.Invoke();
            if (CurrentLap > totalLaps && !IsFinished)
            {
                IsRaceActive = false;
                IsFinished = true;
                OnRaceFinished?.Invoke();
            }
        }

        private void HandleCheckpointPassed()
        {
            OnCheckpointPassed?.Invoke();
        }

        void OnDestroy()
        {
            if (_registeredRuntime != null)
                _registeredRuntime.UnregisterFactory(this);
            if (lapCounter == null)
                return;
            lapCounter.OnCheckpointPassed -= HandleCheckpointPassed;
            lapCounter.OnLapCompleted -= HandleLapCompleted;
            lapCounter.OnStateChanged -= PublishState;
        }

        private void PublishState()
        {
            OnStateChanged?.Invoke();
            Debug.Log(
                "[RACING_STATE] speed=" + VehicleSpeed.ToString("F1") +
                " lap=" + CurrentLap +
                " checkpoints=" + CheckpointsPassed +
                " active=" + IsRaceActive +
                " finished=" + IsFinished);
        }
    }
}
