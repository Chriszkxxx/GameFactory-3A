using UnityEngine;

namespace RacingExample
{
    /// <summary>
    /// A trigger volume that records checkpoint passage for racing vehicles.
    /// When a vehicle enters the trigger, the vehicle's
    /// <see cref="RacingLapCounter"/> (or this checkpoint's assigned counter)
    /// records the checkpoint pass.
    /// </summary>
    [AddComponentMenu("3AGameFactory/Racing Checkpoint")]
    [DisallowMultipleComponent]
    public class RacingCheckpoint : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private int checkpointIndex = 0;
        [SerializeField] private RacingLapCounter lapCounter;

        /// <summary>
        /// Sequential index of this checkpoint on the track (0-based).
        /// </summary>
        public int CheckpointIndex
        {
            get => checkpointIndex;
            set => checkpointIndex = value;
        }

        /// <summary>The lap counter to notify when this checkpoint is passed.</summary>
        public RacingLapCounter LapCounter
        {
            get => lapCounter;
            set => lapCounter = value;
        }

        /// <summary>
        /// Called by Unity when a trigger collider enters this volume. Passes
        /// the checkpoint to the vehicle's lap counter (or this checkpoint's
        /// assigned counter as a fallback).
        /// </summary>
        void OnTriggerEnter(Collider other)
        {
            var vehicle = other.GetComponentInParent<RacingVehicleController>();
            if (vehicle == null)
                return;

            var counter = vehicle.LapCounter ?? lapCounter;
            if (counter != null)
                counter.PassCheckpoint(checkpointIndex);
        }

        /// <summary>
        /// Manually pass this checkpoint to a specific lap counter. Used by
        /// tests and scripted sequences that don't rely on physics triggers.
        /// </summary>
        public void Pass(RacingLapCounter counter)
        {
            if (counter != null)
                counter.PassCheckpoint(checkpointIndex);
        }
    }
}
