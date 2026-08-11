using NUnit.Framework;
using UnityEngine;
using ArenaFighterExample;

namespace ArenaFighterExample.Tests
{
    /// <summary>
    /// EditMode tests for the ArenaFighterExample gameplay plugin.
    /// Each test creates real GameObjects and verifies behavioral invariants.
    /// </summary>
    public class ArenaFighterTests
    {
        private GameObject _attackerGo;
        private GameObject _targetGo;
        private ArenaFighterController _attacker;
        private ArenaFighterController _target;

        [SetUp]
        public void SetUp()
        {
            _attackerGo = new GameObject("Attacker");
            _targetGo = new GameObject("Target");
            _attacker = _attackerGo.AddComponent<ArenaFighterController>();
            _target = _targetGo.AddComponent<ArenaFighterController>();

            // Place target within the default attack range (2 units).
            _attackerGo.transform.position = Vector3.zero;
            _targetGo.transform.position = new Vector3(0f, 0f, 1.5f);
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(_attackerGo);
            Object.DestroyImmediate(_targetGo);
        }

        // ── Required invariant tests ─────────────────────────────────────────

        [Test]
        public void Attack_ReducesTargetHealthByAttackDamage()
        {
            float hpBefore = _target.Health;
            Assert.AreEqual(100f, hpBefore, "Default health should be 100.");
            Assert.AreEqual(10f, _attacker.AttackDamage, "Default attack damage should be 10.");

            bool connected = _attacker.Attack(_target);

            Assert.IsTrue(connected, "Attack should connect when in range.");
            Assert.AreEqual(
                hpBefore - _attacker.AttackDamage,
                _target.Health,
                0.001f,
                "Target health should be reduced by the attacker's AttackDamage.");
        }

        [Test]
        public void Health_ReachingZero_TriggersIsDead()
        {
            // Default health = 100, attack damage = 10 → 10 hits to kill.
            for (int i = 0; i < 10; i++)
            {
                Assert.IsFalse(_target.IsDead,
                    "Fighter should still be alive before health hits zero.");
                _attacker.Attack(_target);
            }

            Assert.IsTrue(_target.IsDead,
                "Fighter should be dead when health reaches zero.");
            Assert.AreEqual(0f, _target.Health, 0.001f,
                "Dead fighter's health should be clamped to zero.");
        }

        // ── Additional invariant tests ────────────────────────────────────────

        [Test]
        public void TakeDamage_ReducesHealthByAmount()
        {
            _target.TakeDamage(30f);
            Assert.AreEqual(70f, _target.Health, 0.001f);
        }

        [Test]
        public void TakeDamage_DoesNotReduceHealthBelowZero()
        {
            _target.TakeDamage(999f);
            Assert.AreEqual(0f, _target.Health, 0.001f);
            Assert.IsTrue(_target.IsDead);
        }

        [Test]
        public void DeadFighter_CannotBeDamaged()
        {
            _target.TakeDamage(100f);
            Assert.IsTrue(_target.IsDead);

            float hp = _target.Health;
            _target.TakeDamage(50f);
            Assert.AreEqual(hp, _target.Health, 0.001f,
                "Dead fighter should not take further damage.");
        }

        [Test]
        public void DeadFighter_CannotAttack()
        {
            _attacker.TakeDamage(100f);
            Assert.IsTrue(_attacker.IsDead);

            bool connected = _attacker.Attack(_target);

            Assert.IsFalse(connected, "Dead fighter should not be able to attack.");
            Assert.AreEqual(100f, _target.Health, 0.001f,
                "Target health should be unchanged when attacked by a dead fighter.");
        }

        [Test]
        public void Attack_OutOfRange_DoesNotConnect()
        {
            _targetGo.transform.position = new Vector3(0f, 0f, 10f);

            bool connected = _attacker.Attack(_target);

            Assert.IsFalse(connected, "Attack should not connect when out of range.");
            Assert.AreEqual(100f, _target.Health, 0.001f,
                "Target health should be unchanged when out of range.");
        }

        [Test]
        public void ResetFighter_RestoresFullHealth()
        {
            _target.TakeDamage(50f);
            Assert.AreEqual(50f, _target.Health, 0.001f);

            _target.ResetFighter();

            Assert.AreEqual(100f, _target.Health, 0.001f);
            Assert.IsFalse(_target.IsDead, "ResetFighter should clear the dead flag.");
        }

        [Test]
        public void ArenaFighterCombat_IsInRange_ReturnsTrueWhenClose()
        {
            Assert.IsTrue(ArenaFighterCombat.IsInRange(_attacker, _target));
        }

        [Test]
        public void ArenaFighterCombat_IsInRange_ReturnsFalseWhenFar()
        {
            _targetGo.transform.position = new Vector3(0f, 0f, 10f);
            Assert.IsFalse(ArenaFighterCombat.IsInRange(_attacker, _target));
        }

        [Test]
        public void ArenaFighterCombat_IsInRange_ReturnsFalseWhenDead()
        {
            _target.TakeDamage(100f);
            Assert.IsFalse(ArenaFighterCombat.IsInRange(_attacker, _target),
                "IsInRange should return false when the target is dead.");
        }
    }
}
