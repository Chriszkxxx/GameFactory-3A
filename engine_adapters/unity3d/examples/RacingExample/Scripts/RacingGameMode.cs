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
    [AddComponentMenu("AAAGameForge/Racing GameMode")]
    public class RacingGameMode : MonoBehaviour
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

        /// <summary>Runtime vehicle controller.</summary>
        public RacingVehicleController Vehicle { get; private set; }

        /// <summary>Whether the race is active.</summary>
        public bool IsRaceActive { get; private set; }

        /// <summary>Whether the race is finished.</summary>
        public bool IsFinished { get; private set; }

        /// <summary>Target number of laps.</summary>
        public int TotalLaps => totalLaps;

        /// <summary>The lap counter used by this GameMode.</summary>
        public RacingLapCounter LapCounter => lapCounter;

        void Awake()
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
            SpawnVehicle();
            ConfigureCheckpoints();
            IsRaceActive = true;
            IsFinished = false;
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

            Vehicle = obj.GetComponent<RacingVehicleController>();
            if (Vehicle == null)
                Vehicle = obj.AddComponent<RacingVehicleController>();

            Vehicle.LapCounter = lapCounter;

            TryRegisterWithRuntime(Vehicle);
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

        private void TryRegisterWithRuntime(RacingVehicleController vehicle)
        {
            var runtime = A3GameRuntimeSubsystem.Instance;
            if (runtime == null)
                return;

            // Attach the runtime entity component so the vehicle is observable
            // through the A3GameRuntime session/snapshot pipeline.
            var entity = vehicle.GetComponent<A3GameRuntimeEntityComponent>();
            if (entity == null)
                entity = vehicle.gameObject.AddComponent<A3GameRuntimeEntityComponent>();
            entity.Initialize(
                A3GameRuntimeSubsystem.NewId("vehicle"),
                runtime.worldId);
        }

        void Update()
        {
            if (!IsRaceActive)
                return;

            if (lapCounter.CurrentLap > totalLaps)
            {
                IsRaceActive = false;
                IsFinished = true;
            }
        }

        /// <summary>Restart the race from the spawn point.</summary>
        public void Restart()
        {
            if (Vehicle != null)
            {
                Vehicle.ResetVehicle();
                Vehicle.transform.position = vehicleSpawn.position;
                Vehicle.transform.rotation = vehicleSpawn.rotation;
            }

            lapCounter.ResetCounter();
            IsRaceActive = true;
            IsFinished = false;
        }
    }
}
