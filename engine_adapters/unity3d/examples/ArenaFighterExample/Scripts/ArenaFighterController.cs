using A3GameRuntime;
using UnityEngine;

namespace ArenaFighterExample
{
    /// <summary>
    /// A melee arena fighter with health, movement, and attack capabilities.
    /// Implements <see cref="IA3GameControllableEntity"/> so it can be driven
    /// by the A3GameRuntime input pipeline, while keeping all gameplay logic
    /// self-contained and unit-testable.
    /// </summary>
    [AddComponentMenu("AAAGameForge/Arena Fighter Controller")]
    [DisallowMultipleComponent]
    public class ArenaFighterController : MonoBehaviour, IA3GameControllableEntity
    {
        [Header("Stats")]
        [SerializeField] private float maxHealth = 100f;
        [SerializeField] private float attackDamage = 10f;
        [SerializeField] private float attackRange = 2f;
        [SerializeField] private float moveSpeed = 5f;

        [Header("Identity")]
        [HideInInspector] public string entityId = string.Empty;

        private const float DefaultMaxHealth = 100f;
        private const float DefaultAttackDamage = 10f;
        private const float DefaultAttackRange = 2f;
        private const float DefaultMoveSpeed = 5f;

        private float _health = DefaultMaxHealth;
        private bool _isDead;

        /// <summary>Current health, clamped to [0, MaxHealth].</summary>
        public float Health
        {
            get => _health;
            private set => _health = value;
        }

        /// <summary>Maximum health this fighter can have.</summary>
        public float MaxHealth => maxHealth > 0f ? maxHealth : 100f;

        /// <summary>Damage dealt per successful attack.</summary>
        public float AttackDamage => attackDamage > 0f ? attackDamage : 10f;

        /// <summary>Maximum distance at which an attack connects.</summary>
        public float AttackRange => attackRange > 0f ? attackRange : 2f;

        /// <summary>Movement speed in world units per second.</summary>
        public float MoveSpeed => moveSpeed > 0f ? moveSpeed : 5f;

        /// <summary>Whether this fighter has been defeated.</summary>
        public bool IsDead
        {
            get => _isDead;
            private set => _isDead = value;
        }

        /// <summary>Health as a 0..1 fraction (for HUD bars).</summary>
        public float HealthFraction =>
            MaxHealth > 0f ? Mathf.Clamp01(Health / MaxHealth) : 0f;

        void Awake()
        {
            // Lazy initialization handles defaults; Awake only clamps
            // serialized fields that Unity may have reset to zero.
            if (maxHealth <= 0f) maxHealth = 100f;
            if (attackDamage <= 0f) attackDamage = 10f;
            if (attackRange <= 0f) attackRange = 2f;
            if (moveSpeed <= 0f) moveSpeed = 5f;
        }

        /// <summary>
        /// Apply damage to this fighter. Triggers death when health reaches
        /// zero. Damage is ignored if the fighter is already dead or the
        /// amount is non-positive.
        /// </summary>
        public void TakeDamage(float amount)
        {
            if (IsDead || amount <= 0f)
                return;

            Health -= amount;
            if (Health <= 0f)
            {
                Health = 0f;
                Die();
            }
        }

        /// <summary>
        /// Perform a melee attack on <paramref name="target"/>. Delegates
        /// range checking to <see cref="ArenaFighterCombat"/>. Returns
        /// <c>true</c> if the attack connected.
        /// </summary>
        public bool Attack(ArenaFighterController target)
        {
            if (IsDead || target == null || target.IsDead)
                return false;

            return ArenaFighterCombat.TryAttack(this, target);
        }

        /// <summary>Mark this fighter as dead and zero its health.</summary>
        public void Die()
        {
            if (IsDead)
                return;
            IsDead = true;
            Health = 0f;
        }

        /// <summary>
        /// Restore the fighter to full health and clear the dead flag. Used by
        /// the GameMode when restarting a round.
        /// </summary>
        public void ResetFighter()
        {
            Health = maxHealth > 0f ? maxHealth : DefaultMaxHealth;
            IsDead = false;
        }

        /// <summary>
        /// Move toward <paramref name="destination"/> using MoveSpeed.
        /// Rotation is updated to face the movement direction. Movement is
        /// confined to the horizontal plane.
        /// </summary>
        public void MoveTo(Vector3 destination, float deltaTime)
        {
            if (IsDead)
                return;

            Vector3 toTarget = destination - transform.position;
            toTarget.y = 0f; // keep movement on the horizontal plane

            if (toTarget.sqrMagnitude < 0.0001f)
                return;

            Vector3 dir = toTarget.normalized;
            float step = moveSpeed * deltaTime;

            // Don't overshoot the destination.
            if (step * step >= toTarget.sqrMagnitude)
                transform.position = destination;
            else
                transform.position += dir * step;

            transform.rotation = Quaternion.LookRotation(dir);
        }

        // ── IA3GameControllableEntity ────────────────────────────────────────

        /// <summary>Return the stable runtime entity identifier.</summary>
        public string GetEntityId() => entityId;

        /// <summary>
        /// Apply a normalized runtime input tick. Rotates the fighter to the
        /// input yaw/pitch and moves along its local forward/right vectors.
        /// Returns <c>false</c> if the fighter is dead.
        /// </summary>
        public bool ApplyInput(A3GameRuntimeInputState input)
        {
            if (IsDead)
                return false;

            // Face the camera orientation.
            transform.rotation = Quaternion.Euler(input.pitch, input.yaw, 0f);

            float mx = Mathf.Clamp(input.move_x, -1f, 1f);
            float my = Mathf.Clamp(input.move_y, -1f, 1f);
            Vector3 move = transform.forward * my + transform.right * mx;

            if (move.sqrMagnitude > 0.0001f)
            {
                float speed = input.run ? moveSpeed * 1.5f : moveSpeed;
                // Approximate one frame at 60 fps for a single input tick.
                transform.position += move.normalized * speed * 0.0166f;
            }

            return true;
        }

        /// <summary>Reset entity to spawn state (IA3GameControllableEntity).</summary>
        public void ResetEntity() => ResetFighter();

        /// <summary>
        /// Return a serializable snapshot of this fighter for the runtime
        /// observation pipeline.
        /// </summary>
        public A3GameEntitySnapshot GetSnapshot()
        {
            return new A3GameEntitySnapshot
            {
                entity_id = entityId,
                actor_label = gameObject.name,
                locomotion_state = IsDead
                    ? A3GameLocomotionState.Idle
                    : A3GameLocomotionState.Walk,
                motion_state = IsDead ? "dead" : "idle",
                position = transform.position,
                rotation = transform.eulerAngles,
            };
        }
    }
}
