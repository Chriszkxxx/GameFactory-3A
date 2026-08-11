using NUnit.Framework;
using UnityEngine;
using RacingExample;

namespace RacingExample.Tests
{
    /// <summary>
    /// EditMode tests for the RacingExample gameplay plugin.
    /// Each test creates real GameObjects and verifies behavioral invariants.
    /// </summary>
    public class RacingTests
    {
        private GameObject _counterGo;
        private RacingLapCounter _lapCounter;

        [SetUp]
        public void SetUp()
        {
            _counterGo = new GameObject("LapCounter");
            _lapCounter = _counterGo.AddComponent<RacingLapCounter>();
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(_counterGo);
        }

        // ── Required invariant tests ─────────────────────────────────────────

        [Test]
        public void PassCheckpoint_IncrementsCheckpointsPassed()
        {
            Assert.AreEqual(0, _lapCounter.CheckpointsPassed,
                "No checkpoints should be passed initially.");

            _lapCounter.PassCheckpoint();

            Assert.AreEqual(1, _lapCounter.CheckpointsPassed,
                "Passing a checkpoint should increment CheckpointsPassed.");
        }

        [Test]
        public void PassingAllCheckpoints_IncrementsCurrentLap()
        {
            _lapCounter.Configure(3, 1);
            Assert.AreEqual(1, _lapCounter.CurrentLap,
                "CurrentLap should start at 1.");

            // Pass all 3 checkpoints.
            _lapCounter.PassCheckpoint();
            _lapCounter.PassCheckpoint();
            _lapCounter.PassCheckpoint();

            Assert.AreEqual(2, _lapCounter.CurrentLap,
                "Passing all checkpoints should increment CurrentLap.");
            Assert.AreEqual(0, _lapCounter.CheckpointsPassed,
                "CheckpointsPassed should reset to 0 after a lap is completed.");
        }

        // ── Additional invariant tests ────────────────────────────────────────

        [Test]
        public void CurrentLap_StartsAtOne()
        {
            Assert.AreEqual(1, _lapCounter.CurrentLap,
                "CurrentLap should default to 1.");
        }

        [Test]
        public void CheckpointsPassed_StartsAtZero()
        {
            Assert.AreEqual(0, _lapCounter.CheckpointsPassed,
                "CheckpointsPassed should default to 0.");
        }

        [Test]
        public void TotalCheckpoints_MatchesConfiguration()
        {
            _lapCounter.Configure(5, 1);
            Assert.AreEqual(5, _lapCounter.TotalCheckpoints);
        }

        [Test]
        public void ResetCounter_RestoresInitialState()
        {
            _lapCounter.Configure(3, 1);
            _lapCounter.PassCheckpoint();
            _lapCounter.PassCheckpoint();

            _lapCounter.ResetCounter();

            Assert.AreEqual(1, _lapCounter.CurrentLap);
            Assert.AreEqual(0, _lapCounter.CheckpointsPassed);
        }

        [Test]
        public void MultipleLaps_IncrementCorrectly()
        {
            _lapCounter.Configure(2, 1);

            // Lap 1: pass 2 checkpoints → lap 2.
            _lapCounter.PassCheckpoint();
            _lapCounter.PassCheckpoint();
            Assert.AreEqual(2, _lapCounter.CurrentLap);

            // Lap 2: pass 2 checkpoints → lap 3.
            _lapCounter.PassCheckpoint();
            _lapCounter.PassCheckpoint();
            Assert.AreEqual(3, _lapCounter.CurrentLap);
        }

        [Test]
        public void Vehicle_CurrentLap_DelegatesToCounter()
        {
            var vehicleGo = new GameObject("Vehicle");
            var vehicle = vehicleGo.AddComponent<RacingVehicleController>();
            vehicle.LapCounter = _lapCounter;

            Assert.AreEqual(1, vehicle.CurrentLap,
                "Vehicle CurrentLap should reflect the lap counter's initial value.");

            _lapCounter.Configure(2, 1);
            _lapCounter.PassCheckpoint();
            _lapCounter.PassCheckpoint();

            Assert.AreEqual(2, vehicle.CurrentLap,
                "Vehicle CurrentLap should update when the lap counter advances.");

            Object.DestroyImmediate(vehicleGo);
        }

        [Test]
        public void Vehicle_CurrentLap_DefaultsToOneWithoutCounter()
        {
            var vehicleGo = new GameObject("Vehicle");
            var vehicle = vehicleGo.AddComponent<RacingVehicleController>();

            Assert.AreEqual(1, vehicle.CurrentLap,
                "Vehicle CurrentLap should default to 1 when no lap counter is assigned.");

            Object.DestroyImmediate(vehicleGo);
        }

        [Test]
        public void Vehicle_Accelerate_IncreasesSpeed()
        {
            var vehicleGo = new GameObject("Vehicle");
            var vehicle = vehicleGo.AddComponent<RacingVehicleController>();

            Assert.AreEqual(0f, vehicle.Speed);
            Assert.IsFalse(vehicle.IsMoving);

            vehicle.Accelerate(1f);

            Assert.Greater(vehicle.Speed, 0f,
                "Accelerating should increase speed.");
            Assert.IsTrue(vehicle.IsMoving, "Vehicle should be moving after accelerating.");

            Object.DestroyImmediate(vehicleGo);
        }

        [Test]
        public void Vehicle_Brake_DecreasesSpeed()
        {
            var vehicleGo = new GameObject("Vehicle");
            var vehicle = vehicleGo.AddComponent<RacingVehicleController>();

            vehicle.Accelerate(1f);
            float speedAfterAccel = vehicle.Speed;

            vehicle.Brake(0.5f);

            Assert.Less(vehicle.Speed, speedAfterAccel,
                "Braking should decrease speed.");

            Object.DestroyImmediate(vehicleGo);
        }

        [Test]
        public void RacingCheckpoint_Pass_NotifyLapCounter()
        {
            var checkpointGo = new GameObject("Checkpoint");
            var checkpoint = checkpointGo.AddComponent<RacingCheckpoint>();
            checkpoint.LapCounter = _lapCounter;

            Assert.AreEqual(0, _lapCounter.CheckpointsPassed);

            checkpoint.Pass(_lapCounter);

            Assert.AreEqual(1, _lapCounter.CheckpointsPassed,
                "RacingCheckpoint.Pass should notify the lap counter.");

            Object.DestroyImmediate(checkpointGo);
        }
    }
}
