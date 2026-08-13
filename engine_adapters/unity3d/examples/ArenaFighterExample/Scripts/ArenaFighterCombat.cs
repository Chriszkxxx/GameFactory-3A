using UnityEngine;

namespace ArenaFighterExample
{
    /// <summary>
    /// Static helper that resolves melee hit detection between two
    /// <see cref="ArenaFighterController"/> instances. Centralising the
    /// range check keeps combat logic deterministic and testable without
    /// relying on Unity's physics engine.
    /// </summary>
    public static class ArenaFighterCombat
    {
        /// <summary>
        /// Returns <c>true</c> when <paramref name="attacker"/> is within
        /// its own <see cref="ArenaFighterController.AttackRange"/> of
        /// <paramref name="target"/> and both fighters are alive.
        /// </summary>
        public static bool IsInRange(ArenaFighterController attacker,
                                     ArenaFighterController target)
        {
            if (attacker == null || target == null)
                return false;
            if (attacker.IsDead || target.IsDead)
                return false;

            float distance = Vector3.Distance(
                attacker.transform.position,
                target.transform.position);
            return distance <= attacker.AttackRange;
        }

        /// <summary>
        /// If <paramref name="attacker"/> is in range of
        /// <paramref name="target"/>, apply the attacker's damage to the
        /// target and return <c>true</c>. Returns <c>false</c> if the attack
        /// does not connect.
        /// </summary>
        public static bool TryAttack(ArenaFighterController attacker,
                                     ArenaFighterController target)
        {
            if (!IsInRange(attacker, target))
                return false;

            target.TakeDamage(attacker.AttackDamage);
            return true;
        }

        /// <summary>
        /// Return the straight-line distance between two fighters, or
        /// <see cref="float.MaxValue"/> if either is null.
        /// </summary>
        public static float Distance(ArenaFighterController a,
                                     ArenaFighterController b)
        {
            if (a == null || b == null)
                return float.MaxValue;
            return Vector3.Distance(
                a.transform.position,
                b.transform.position);
        }
    }
}
