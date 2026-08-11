using NUnit.Framework;
using UnityEngine;

namespace FPSExample.Tests
{
    public sealed class FPSArenaTests
    {
        private GameObject weaponObject;
        private GameObject enemyObject;
        private GameObject stateObject;
        private FPSWeapon weapon;
        private FPSEnemy enemy;
        private FPSGameState state;

        [SetUp]
        public void SetUp()
        {
            weaponObject = new GameObject("WeaponTest");
            enemyObject = new GameObject("EnemyTest");
            stateObject = new GameObject("StateTest");
            weapon = weaponObject.AddComponent<FPSWeapon>();
            enemy = enemyObject.AddComponent<FPSEnemy>();
            state = stateObject.AddComponent<FPSGameState>();
            weapon.ResetWeapon();
            enemy.ResetEnemy();
            state.ResetState();
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(weaponObject);
            Object.DestroyImmediate(enemyObject);
            Object.DestroyImmediate(stateObject);
        }

        [Test]
        public void FiringReducesEnemyHealthByTwentyFive()
        {
            Assert.That(weapon.FireAt(enemy), Is.True);
            Assert.That(enemy.Health, Is.EqualTo(25f).Within(0.001f));
            Assert.That(weapon.AmmoInMagazine, Is.EqualTo(29));
        }

        [Test]
        public void EnemyAtZeroHealthDiesAndTriggersDeathAnimationState()
        {
            Assert.That(enemy.TakeDamage(50f), Is.True);
            Assert.That(enemy.Health, Is.Zero);
            Assert.That(enemy.IsDead, Is.True);
            Assert.That(enemy.DeathAnimationTriggered, Is.True);
        }

        [Test]
        public void PlayerAtZeroHealthLosesGame()
        {
            Assert.That(state.DamagePlayer(100f), Is.True);
            Assert.That(state.PlayerHealth, Is.Zero);
            Assert.That(state.Status, Is.EqualTo(FPSGameStatus.Lost));
        }

        [Test]
        public void ThirdEnemyKillWinsGame()
        {
            state.RegisterEnemyKill();
            state.RegisterEnemyKill();
            Assert.That(state.Status, Is.EqualTo(FPSGameStatus.Playing));
            state.RegisterEnemyKill();
            Assert.That(state.Status, Is.EqualTo(FPSGameStatus.Won));
            Assert.That(state.EnemiesKilled, Is.EqualTo(3));
        }

        [Test]
        public void ReloadBlocksFireUntilTwoSecondsComplete()
        {
            Assert.That(weapon.FireAt(enemy), Is.True);
            weapon.Tick(weapon.FireCooldown);
            Assert.That(weapon.StartReload(), Is.True);
            Assert.That(weapon.FireAt(enemy), Is.False);
            weapon.Tick(1.99f);
            Assert.That(weapon.FireAt(enemy), Is.False);
            weapon.Tick(0.01f);
            Assert.That(weapon.FireAt(enemy), Is.True);
            Assert.That(weapon.AmmoInMagazine, Is.EqualTo(29));
        }

        [Test]
        public void DeadEnemyCannotBeDamagedAgain()
        {
            enemy.TakeDamage(50f);
            Assert.That(weapon.FireAt(enemy), Is.False);
            Assert.That(enemy.Health, Is.Zero);
        }

        [Test]
        public void FireCooldownEnforcesFourShotsPerSecond()
        {
            Assert.That(weapon.FireAt(enemy), Is.True);
            Assert.That(weapon.FireAt(enemy), Is.False);
            weapon.Tick(0.249f);
            Assert.That(weapon.FireAt(enemy), Is.False);
            weapon.Tick(0.001f);
            Assert.That(weapon.FireAt(enemy), Is.True);
            Assert.That(enemy.IsDead, Is.True);
        }

        [Test]
        public void ContactDamageIsTenPerSecond()
        {
            enemyObject.transform.position = Vector3.zero;
            float damage = enemy.TickTowards(Vector3.zero, 0.5f);
            Assert.That(damage, Is.EqualTo(5f).Within(0.001f));
        }

        [Test]
        public void FullMagazineDoesNotStartReload()
        {
            Assert.That(weapon.StartReload(), Is.False);
            Assert.That(weapon.IsReloading, Is.False);
        }

        [Test]
        public void GameStateEventsExposeObservableChanges()
        {
            int damageEvents = 0;
            int stateEvents = 0;
            state.PlayerDamaged += amount => damageEvents++;
            state.StateChanged += () => stateEvents++;
            state.DamagePlayer(10f);
            Assert.That(damageEvents, Is.EqualTo(1));
            Assert.That(stateEvents, Is.EqualTo(1));
        }

        [Test]
        public void DoorToggleMovesPanelsAndCloseRestoresThem()
        {
            GameObject root = new GameObject("door");
            GameObject left = new GameObject("left_panel");
            GameObject right = new GameObject("right_panel");
            left.transform.SetParent(root.transform, false);
            right.transform.SetParent(root.transform, false);
            left.transform.localPosition = new Vector3(-0.75f, 1.5f, 0f);
            right.transform.localPosition = new Vector3(0.75f, 1.5f, 0f);
            left.AddComponent<BoxCollider>().size = new Vector3(1.5f, 3f, 0.2f);
            right.AddComponent<BoxCollider>().size = new Vector3(1.5f, 3f, 0.2f);
            FPSDoor door = root.AddComponent<FPSDoor>();

            Assert.That(door.ConfigureFromPrefab(), Is.True);
            Vector3 leftClosed = left.transform.localPosition;
            Vector3 rightClosed = right.transform.localPosition;
            door.SetOpen(true, true);
            Assert.That(left.transform.localPosition, Is.Not.EqualTo(leftClosed));
            Assert.That(right.transform.localPosition, Is.Not.EqualTo(rightClosed));
            door.SetOpen(false, true);
            Assert.That(left.transform.localPosition, Is.EqualTo(leftClosed));
            Assert.That(right.transform.localPosition, Is.EqualTo(rightClosed));

            Object.DestroyImmediate(root);
        }
    }
}
