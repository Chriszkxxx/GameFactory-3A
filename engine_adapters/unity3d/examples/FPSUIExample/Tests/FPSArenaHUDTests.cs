using FPSExample;
using NUnit.Framework;
using UnityEngine;

namespace FPSUIExample.Tests
{
    public sealed class FPSArenaHUDTests
    {
        private GameObject adapterObject;
        private GameObject hudObject;
        private FPSGameRuntimeAdapter adapter;
        private FPSArenaHUD hud;

        [SetUp]
        public void SetUp()
        {
            adapterObject = new GameObject("AdapterTest");
            hudObject = new GameObject("HUDTest");
            adapter = adapterObject.AddComponent<FPSGameRuntimeAdapter>();
            hud = hudObject.AddComponent<FPSArenaHUD>();
            adapter.Setup();
            hud.Bind(adapter);
            hud.Refresh();
        }

        [TearDown]
        public void TearDown()
        {
            foreach (FPSEnemy enemy in Object.FindObjectsOfType<FPSEnemy>())
                Object.DestroyImmediate(enemy.gameObject);
            Object.DestroyImmediate(hudObject);
            Object.DestroyImmediate(adapterObject);
        }

        [Test]
        public void InitialStateRendersAllFourBoundValues()
        {
            Assert.That(hud.HealthLabel, Is.EqualTo("HP: 100/100"));
            Assert.That(hud.AmmoLabel, Is.EqualTo("30 / 30"));
            Assert.That(hud.KillLabel, Is.EqualTo("Kills: 0 / 3"));
            Assert.That(hud.TimerLabel, Is.EqualTo("00:60"));
        }

        [Test]
        public void WeaponCommandChangesObservableAmmoDisplay()
        {
            Assert.That(adapter.Shoot(), Is.True);
            hud.Refresh();
            Assert.That(hud.AmmoLabel, Is.EqualTo("29 / 30"));
        }

        [Test]
        public void ReloadEventChangesObservableAmmoDisplay()
        {
            adapter.Shoot();
            Assert.That(adapter.Reload(), Is.True);
            hud.Refresh();
            Assert.That(hud.AmmoLabel, Is.EqualTo("RELOADING..."));
        }

        [Test]
        public void WinAndLosePresentationAreDistinct()
        {
            hud.ShowGameOver(FPSGameStatus.Won);
            Assert.That(hud.GameOverVisible, Is.True);
            Assert.That(hud.GameOverTitle, Is.EqualTo("ARENA CLEARED!"));
            hud.ShowGameOver(FPSGameStatus.Lost);
            Assert.That(hud.GameOverTitle, Is.EqualTo("YOU DIED"));
        }

        [Test]
        public void RestartButtonInvokesPublicResetCommand()
        {
            adapter.Shoot();
            hud.ShowGameOver(FPSGameStatus.Lost);
            hud.RestartButton.onClick.Invoke();
            Assert.That(hud.GameOverVisible, Is.False);
            Assert.That(adapter.PlayerAmmo, Is.EqualTo(30));
            Assert.That(adapter.PlayerHealth, Is.EqualTo(100f));
        }

        [Test]
        public void PresentationHelpersCoverTimerAndHealthGradient()
        {
            Assert.That(FPSArenaHUD.FormatTimer(60f), Is.EqualTo("00:60"));
            Assert.That(FPSArenaHUD.FormatTimer(9.2f), Is.EqualTo("00:10"));
            Color healthy = FPSArenaHUD.HealthColor(1f);
            Color critical = FPSArenaHUD.HealthColor(0f);
            Assert.That(healthy.g, Is.GreaterThan(healthy.r));
            Assert.That(critical.r, Is.GreaterThan(critical.g));
        }
    }
}
