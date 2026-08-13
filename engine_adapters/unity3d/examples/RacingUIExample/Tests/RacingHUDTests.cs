using NUnit.Framework;
using RacingExample;
using UnityEngine;

namespace RacingUIExample.Tests
{
    public sealed class RacingHUDTests
    {
        private GameObject gameObject;
        private GameObject hudObject;
        private RacingGameMode gameMode;
        private RacingHUD hud;

        [SetUp]
        public void SetUp()
        {
            gameObject = new GameObject("RacingGameModeTest");
            hudObject = new GameObject("RacingHUDTest");
            gameMode = gameObject.AddComponent<RacingGameMode>();
            gameMode.Setup();
            hud = hudObject.AddComponent<RacingHUD>();
            hud.Bind(gameMode);
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(hudObject);
            Object.DestroyImmediate(gameObject);
        }

        [Test]
        public void InitialStateRendersMechanicValues()
        {
            Assert.AreEqual("Speed: 0", hud.SpeedLabel);
            Assert.AreEqual("Lap 1 / 3", hud.LapLabel);
            Assert.AreEqual("Checkpoint 0 / 3", hud.CheckpointLabel);
            Assert.IsFalse(hud.ResultVisible);
        }

        [Test]
        public void DriveAndCheckpointEventsRefreshHud()
        {
            gameMode.Drive(1f, 0f, false, 0.5f);
            gameMode.LapCounter.PassCheckpoint(0);

            Assert.AreEqual("Speed: 10", hud.SpeedLabel);
            Assert.AreEqual("Checkpoint 1 / 3", hud.CheckpointLabel);
        }

        [Test]
        public void FinishAndRestartUsePublicMechanicContract()
        {
            for (int lap = 0; lap < gameMode.TotalLaps; lap++)
            {
                for (int checkpoint = 0;
                     checkpoint < gameMode.TotalCheckpoints;
                     checkpoint++)
                    gameMode.LapCounter.PassCheckpoint(checkpoint);
            }

            Assert.IsTrue(gameMode.IsFinished);
            Assert.IsTrue(hud.ResultVisible);
            Assert.AreEqual("RACE FINISHED", hud.ResultLabel);

            hud.RestartButton.onClick.Invoke();

            Assert.IsFalse(gameMode.IsFinished);
            Assert.IsFalse(hud.ResultVisible);
            Assert.AreEqual("Lap 1 / 3", hud.LapLabel);
        }
    }
}
