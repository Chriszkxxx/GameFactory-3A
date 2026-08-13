using System;
using UnityEngine;

namespace FPSExample
{
    [DisallowMultipleComponent]
    public sealed class FPSEnemy : MonoBehaviour
    {
        public const float DefaultHealth = 50f;
        public const float DefaultMoveSpeed = 2f;
        public const float DefaultContactDamagePerSecond = 10f;
        public const float DefaultContactRange = 1.5f;
        public const float DefaultDestroyDelay = 3f;

        [SerializeField] private float maxHealth = DefaultHealth;
        [SerializeField] private float moveSpeed = DefaultMoveSpeed;
        [SerializeField] private float contactDamagePerSecond = DefaultContactDamagePerSecond;
        [SerializeField] private float contactRange = DefaultContactRange;
        [SerializeField] private float destroyDelay = DefaultDestroyDelay;
        [SerializeField] private Animator animator;
        [SerializeField] private string deathTrigger = "Death";
        [SerializeField] private GameObject gunView;
        [SerializeField] private CharacterController characterController;
        [SerializeField] private float gravity = -19.62f;

        private float destroyRemaining;
        private float shotCooldown;
        private float reloadRemaining;
        private int shotsSinceReload;
        private bool walking;
        private float verticalVelocity;

        public float Health { get; private set; }
        public float MaxHealth => Mathf.Max(1f, maxHealth);
        public bool IsDead { get; private set; }
        public bool DeathAnimationTriggered { get; private set; }
        public bool ShouldDestroy => IsDead && destroyRemaining <= 0f;

        public event Action<FPSEnemy> Died;

        public void ConfigurePresentation(
            RuntimeAnimatorController controller,
            GameObject gunPrefab)
        {
            if (animator == null)
                animator = GetComponentInChildren<Animator>();
            if (animator != null)
            {
                animator.runtimeAnimatorController = controller;
                animator.applyRootMotion = false;
                animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                animator.Rebind();
                animator.Update(0f);
                animator.Play("Idle", 0, 0f);
                Debug.Log(
                    "[FPS_ANIMATION] " + name +
                    " avatar=" + (animator.avatar != null ? animator.avatar.name : "missing") +
                    " valid=" + (animator.avatar != null && animator.avatar.isValid) +
                    " human=" + (animator.avatar != null && animator.avatar.isHuman));
            }

            if (gunPrefab == null || gunView != null)
                return;
            Transform hand = animator != null
                ? animator.GetBoneTransform(HumanBodyBones.RightHand)
                : null;
            Transform parent = hand != null ? hand : transform;
            gunView = Instantiate(gunPrefab);
            gunView.name = "Prepared_Gun_EnemyView";
            gunView.transform.SetParent(parent, false);
            gunView.transform.localScale = Vector3.one * 0.42f;
            gunView.transform.position = parent.position + transform.forward * 0.1f;
            gunView.transform.rotation = Quaternion.LookRotation(transform.forward, transform.up);
            Debug.Log("[FPS_WEAPON] " + name + " gun attached to " + parent.name);
        }

        private void Awake()
        {
            if (animator == null)
                animator = GetComponentInChildren<Animator>();
            if (characterController == null)
                characterController = GetComponent<CharacterController>();
            ResetEnemy();
        }

        public void ConfigureCharacterController(CharacterController controller)
        {
            characterController = controller;
            if (characterController == null)
                return;
            characterController.stepOffset = 0.35f;
            characterController.slopeLimit = 50f;
            characterController.skinWidth = 0.04f;
        }

        public bool TakeDamage(float amount)
        {
            if (IsDead || amount <= 0f)
                return false;
            Health = Mathf.Max(0f, Health - amount);
            if (Health <= 0f)
                Die();
            return true;
        }

        private void Die()
        {
            if (IsDead)
                return;
            IsDead = true;
            DeathAnimationTriggered = true;
            destroyRemaining = Mathf.Max(0f, destroyDelay);
            if (animator != null && !string.IsNullOrEmpty(deathTrigger))
            {
                animator.SetFloat("Speed", 0f);
                animator.SetTrigger(deathTrigger);
            }
            Died?.Invoke(this);
        }

        public void ResetEnemy()
        {
            Health = MaxHealth;
            IsDead = false;
            DeathAnimationTriggered = false;
            destroyRemaining = 0f;
            shotCooldown = 0f;
            reloadRemaining = 0f;
            shotsSinceReload = 0;
            verticalVelocity = 0f;
        }

        public float TickTowards(Vector3 playerPosition, float deltaTime)
        {
            if (IsDead)
            {
                destroyRemaining = Mathf.Max(0f, destroyRemaining - Mathf.Max(0f, deltaTime));
                return 0f;
            }
            Vector3 offset = playerPosition - transform.position;
            offset.y = 0f;
            float distance = offset.magnitude;
            if (distance > contactRange && distance > 0.001f)
            {
                transform.rotation = Quaternion.Slerp(
                    transform.rotation,
                    Quaternion.LookRotation(offset.normalized, Vector3.up),
                    Mathf.Clamp01(deltaTime * 8f));
                MoveWithGravity(
                    offset.normalized,
                    Mathf.Min(distance, moveSpeed * deltaTime),
                    deltaTime);
                SetWalking(true);
            }
            else
            {
                MoveWithGravity(Vector3.zero, 0f, deltaTime);
                SetWalking(false);
                AnimateRangedAttack(Mathf.Max(0f, deltaTime));
            }
            if (gunView != null)
                gunView.transform.rotation = Quaternion.LookRotation(
                    transform.forward,
                    transform.up);
            return distance <= contactRange
                ? contactDamagePerSecond * Mathf.Max(0f, deltaTime)
                : 0f;
        }

        private void MoveWithGravity(
            Vector3 direction,
            float planarDistance,
            float deltaTime)
        {
            Vector3 planarStep = direction * Mathf.Max(0f, planarDistance);
            if (characterController != null && characterController.enabled)
            {
                if (characterController.isGrounded && verticalVelocity < 0f)
                    verticalVelocity = -2f;
                else
                    verticalVelocity += gravity * Mathf.Max(0f, deltaTime);
                Vector3 motion = planarStep + Vector3.up * (
                    verticalVelocity * Mathf.Max(0f, deltaTime));
                characterController.Move(motion);
                return;
            }

            transform.position += planarStep;
            if (TryFindWalkableGround(transform.position, out float groundY))
                PlaceFeetAtHeight(groundY);
        }

        private bool TryFindWalkableGround(Vector3 position, out float groundY)
        {
            RaycastHit[] hits = Physics.RaycastAll(
                position + Vector3.up * 2f,
                Vector3.down,
                10f,
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore);
            Array.Sort(hits, (left, right) => left.distance.CompareTo(right.distance));
            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null ||
                    hit.collider.transform.IsChildOf(transform) ||
                    hit.normal.y < 0.55f ||
                    hit.collider.GetType().Name == "TerrainCollider" ||
                    IsGeneratedSafetyCollider(hit.collider.transform))
                    continue;
                groundY = hit.point.y;
                return true;
            }
            groundY = 0f;
            return false;
        }

        private void PlaceFeetAtHeight(float groundY)
        {
            Renderer[] renderers = GetComponentsInChildren<Renderer>(true);
            float bottom = float.PositiveInfinity;
            foreach (Renderer item in renderers)
                if (item != null)
                    bottom = Mathf.Min(bottom, item.bounds.min.y);
            if (!float.IsPositiveInfinity(bottom))
                transform.position += Vector3.up * (groundY - bottom + 0.02f);
        }

        private static bool IsGeneratedSafetyCollider(Transform item)
        {
            for (Transform current = item; current != null; current = current.parent)
                if (current.name == "FPS_InvisibleSafetyBounds")
                    return true;
            return false;
        }

        private void SetWalking(bool value)
        {
            if (animator == null) return;
            animator.SetFloat("Speed", value ? 1f : 0f);
            if (walking == value) return;
            walking = value;
            animator.CrossFadeInFixedTime(value ? "Walk" : "Idle", 0.12f);
        }

        private void AnimateRangedAttack(float deltaTime)
        {
            if (reloadRemaining > 0f)
            {
                reloadRemaining = Mathf.Max(0f, reloadRemaining - deltaTime);
                if (reloadRemaining <= 0f) shotsSinceReload = 0;
                return;
            }

            shotCooldown = Mathf.Max(0f, shotCooldown - deltaTime);
            if (shotCooldown > 0f || animator == null)
                return;
            if (shotsSinceReload >= 4)
            {
                animator.SetTrigger("Reload");
                reloadRemaining = 2f;
                return;
            }
            animator.SetTrigger("Shoot");
            shotsSinceReload++;
            shotCooldown = 0.65f;
        }
    }
}
