using UnityEngine;

namespace ArenaFighterExample
{
    /// <summary>
    /// Simple AI that chases the player and attacks when in range. Designed
    /// to be driven via <see cref="Tick(float)"/> so the behaviour is
    /// identical whether called from Unity's <see cref="Update"/> loop or
    /// from an external controller (useful for deterministic testing).
    /// </summary>
    [AddComponentMenu("AAAGameForge/Arena Fighter AI")]
    [DisallowMultipleComponent]
    public class ArenaFighterAI : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private ArenaFighterController self;
        [SerializeField] private ArenaFighterController player;

        [Header("Behaviour")]
        [SerializeField] private float attackCooldown = 1f;
        [SerializeField] private float stopDistance = 1.5f;

        // Initialised high so the AI can attack on its first eligible tick.
        private float _cooldownTimer = 999f;

        /// <summary>The fighter this AI controls.</summary>
        public ArenaFighterController Self
        {
            get => self;
            set => self = value;
        }

        /// <summary>The player the AI chases.</summary>
        public ArenaFighterController Player
        {
            get => player;
            set => player = value;
        }

        /// <summary>Seconds remaining before the AI can attack again.</summary>
        public float CooldownRemaining => Mathf.Max(0f, attackCooldown - _cooldownTimer);

        void Update()
        {
            Tick(Time.deltaTime);
        }

        /// <summary>
        /// Advance the AI by <paramref name="deltaTime"/> seconds. Moves
        /// toward the player and attacks when in range (respecting cooldown).
        /// </summary>
        public void Tick(float deltaTime)
        {
            if (self == null || self.IsDead)
                return;
            if (player == null || player.IsDead)
                return;

            _cooldownTimer += deltaTime;

            float distance = ArenaFighterCombat.Distance(self, player);

            // Move closer until within stop distance.
            if (distance > stopDistance)
            {
                self.MoveTo(player.transform.position, deltaTime);
            }

            // Attack when in range and cooldown elapsed.
            if (distance <= self.AttackRange && _cooldownTimer >= attackCooldown)
            {
                self.Attack(player);
                _cooldownTimer = 0f;
            }
        }

        /// <summary>
        /// Reset the AI's attack cooldown timer (used when restarting a round).
        /// </summary>
        public void ResetAI()
        {
            _cooldownTimer = 999f;
        }
    }
}
