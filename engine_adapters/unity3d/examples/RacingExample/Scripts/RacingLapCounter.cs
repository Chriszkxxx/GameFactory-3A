using UnityEngine;

namespace RacingExample
{
    /// <summary>
    /// Tracks checkpoint progress and lap counting for a racing vehicle.
    /// <see cref="PassCheckpoint"/> is called by <see cref="RacingCheckpoint"/>
    /// triggers; when all checkpoints have been passed, the counter resets
    /// progress and increments <see cref="CurrentLap"/>.
    /// </summary>
    [AddComponentMenu("AAAGameForge/Racing Lap Counter")]
    [DisallowMultipleComponent]
    public class RacingLapCounter : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private int totalCheckpoints = 3;
        [SerializeField] private int startLap = 1;

        /// <summary>Current lap number (starts at 1).</summary>
        public int CurrentLap { get; private set; }

        /// <summary>Number of checkpoints passed in the current lap.</summary>
        public int CheckpointsPassed { get; private set; }

        /// <summary>Total number of checkpoints in the track.</summary>
        public int TotalCheckpoints => totalCheckpoints;

        /// <summary>Whether all checkpoints have been passed this lap.</summary>
        public bool AllCheckpointsPassed =>
            CheckpointsPassed >= totalCheckpoints;

        /// <summary>
        /// Whether the most recent <see cref="PassCheckpoint"/> call completed
        /// a lap. Reset to false at the start of each PassCheckpoint call.
        /// </summary>
        public bool LapJustCompleted { get; private set; }

        void Awake()
        {
            ResetCounter();
        }

        /// <summary>
        /// Record passage of a checkpoint. Increments
        /// <see cref="CheckpointsPassed"/>. When all checkpoints have been
        /// passed, resets CheckpointsPassed to zero and increments
        /// <see cref="CurrentLap"/>.
        /// </summary>
        public void PassCheckpoint()
        {
            LapJustCompleted = false;

            CheckpointsPassed++;

            if (CheckpointsPassed >= totalCheckpoints)
            {
                CheckpointsPassed = 0;
                CurrentLap++;
                LapJustCompleted = true;
            }
        }

        /// <summary>
        /// Configure the total number of checkpoints and starting lap, then
        /// reset the counter.
        /// </summary>
        public void Configure(int total, int lap = 1)
        {
            totalCheckpoints = Mathf.Max(1, total);
            startLap = Mathf.Max(1, lap);
            ResetCounter();
        }

        /// <summary>Reset the lap counter to its starting state.</summary>
        public void ResetCounter()
        {
            CurrentLap = startLap;
            CheckpointsPassed = 0;
            LapJustCompleted = false;
        }
    }
}
