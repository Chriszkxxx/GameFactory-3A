using System;
using UnityEngine;

namespace FPSExample
{
    [RequireComponent(typeof(CharacterController))]
    [DisallowMultipleComponent]
    public sealed class FPSPlayerController : MonoBehaviour
    {
        public const float DefaultMoveSpeed = 5f;
        public const float DefaultEyeHeight = 1.7f;
        public const float DefaultShootRange = 100f;

        [SerializeField] private float moveSpeed = DefaultMoveSpeed;
        [SerializeField] private float gravity = -19.62f;
        [SerializeField] private float jumpHeight = 1.25f;
        [SerializeField] private float lookSensitivity = 2f;
        [SerializeField] private float eyeHeight = DefaultEyeHeight;
        [SerializeField] private float shootRange = DefaultShootRange;
        [SerializeField] private float fallResetDistance = 12f;
        [SerializeField] private CharacterController characterController;
        [SerializeField] private Camera playerCamera;
        [SerializeField] private FPSWeapon weapon;

        private float verticalVelocity;
        private Vector3 respawnPosition;
        private bool hasRespawnPosition;

        public float Yaw { get; private set; }
        public float Pitch { get; private set; }
        public float EyeHeight => eyeHeight;
        public FPSWeapon Weapon => weapon;
        public Camera PlayerCamera => playerCamera;
        public bool IsGrounded =>
            characterController != null &&
            (characterController.isGrounded || HasWalkableGroundBelow(0.25f));

        private void Awake()
        {
            EnsureCharacterController();
            Yaw = transform.eulerAngles.y;
            if (weapon == null)
                weapon = GetComponent<FPSWeapon>();
        }

        public void Configure(Camera camera, FPSWeapon equippedWeapon)
        {
            EnsureCharacterController();
            playerCamera = camera;
            weapon = equippedWeapon;
        }

        private void EnsureCharacterController()
        {
            if (characterController == null)
                characterController = GetComponent<CharacterController>();
            if (characterController == null)
                characterController = gameObject.AddComponent<CharacterController>();
            characterController.height = 1.8f;
            characterController.radius = 0.35f;
            characterController.center = new Vector3(0f, 0.9f, 0f);
            characterController.stepOffset = 0.35f;
            characterController.slopeLimit = 50f;
        }

        public void SetInitialView(Vector3 eulerAngles)
        {
            Yaw = eulerAngles.y;
            Pitch = Mathf.Clamp(NormalizePitch(eulerAngles.x), -89f, 89f);
            transform.rotation = Quaternion.Euler(0f, Yaw, 0f);
            if (playerCamera != null)
                playerCamera.transform.localRotation = Quaternion.Euler(Pitch, 0f, 0f);
        }

        public bool SnapToGround(float maxDistance = 20f)
        {
            Vector3 referencePosition = transform.position;
            Vector3 origin = referencePosition + Vector3.up * 4f;
            RaycastHit[] hits = Physics.RaycastAll(
                origin,
                Vector3.down,
                Mathf.Max(5f, maxDistance + 4f),
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore);
            FPSPhysicsOrder.SortHits(hits);
            RaycastHit? terrainFallback = null;
            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null ||
                    hit.collider.transform.IsChildOf(transform) ||
                    hit.normal.y < 0.55f ||
                    hit.point.y > referencePosition.y + 0.75f)
                    continue;
                if (hit.collider.GetType().Name == "TerrainCollider")
                {
                    if (!terrainFallback.HasValue) terrainFallback = hit;
                    continue;
                }
                Warp(hit.point + Vector3.up * 0.05f);
                respawnPosition = transform.position;
                hasRespawnPosition = true;
                Debug.Log(
                    "[FPS_GROUND] Player grounded on " + hit.collider.name +
                    " at " + hit.point + " normal=" + hit.normal);
                return true;
            }

            Collider preparedFloor = FindNearestPreparedFloor(referencePosition);
            if (preparedFloor != null)
            {
                Bounds bounds = preparedFloor.bounds;
                Warp(new Vector3(bounds.center.x, bounds.max.y + 0.05f, bounds.center.z));
                respawnPosition = transform.position;
                hasRespawnPosition = true;
                Debug.Log(
                    "[FPS_GROUND] Player moved to nearest prepared floor " +
                    preparedFloor.name + " at " + transform.position);
                return true;
            }

            if (terrainFallback.HasValue)
            {
                RaycastHit hit = terrainFallback.Value;
                Warp(hit.point + Vector3.up * 0.05f);
                respawnPosition = transform.position;
                hasRespawnPosition = true;
                Debug.Log(
                    "[FPS_GROUND] Player grounded on terrain collider " + hit.collider.name +
                    " at " + hit.point + " normal=" + hit.normal);
                return true;
            }

            Terrain terrain = Terrain.activeTerrain;
            if (terrain != null)
            {
                float groundY = terrain.SampleHeight(referencePosition) + terrain.transform.position.y;
                Warp(new Vector3(referencePosition.x, groundY + 0.05f, referencePosition.z));
                Debug.Log("[FPS_GROUND] Player used Terrain.SampleHeight fallback at y=" + groundY.ToString("F3"));
            }
            respawnPosition = transform.position;
            hasRespawnPosition = true;
            return terrain != null;
        }

        private static Collider FindNearestPreparedFloor(Vector3 referencePosition)
        {
            Collider best = null;
            float bestDistance = float.PositiveInfinity;
            foreach (Collider collider in FPSPhysicsOrder.FindColliders())
            {
                if (collider == null || !collider.enabled || collider.isTrigger)
                    continue;
                string normalized = collider.name.ToLowerInvariant();
                if (!normalized.Contains("floor") ||
                    normalized.Contains("safety") ||
                    collider.GetComponentInParent<FPSGameRuntimeAdapter>() != null)
                    continue;
                Vector3 center = collider.bounds.center;
                float distance =
                    (center.x - referencePosition.x) * (center.x - referencePosition.x) +
                    (center.z - referencePosition.z) * (center.z - referencePosition.z);
                if (distance >= bestDistance)
                    continue;
                best = collider;
                bestDistance = distance;
            }
            return best;
        }

        public void Respawn()
        {
            if (!hasRespawnPosition)
            {
                respawnPosition = transform.position;
                hasRespawnPosition = true;
            }
            Warp(respawnPosition);
        }

        public void Move(Vector2 input, float deltaTime)
        {
            EnsureCharacterController();
            Vector3 planar = transform.forward * input.y + transform.right * input.x;
            if (planar.sqrMagnitude > 1f)
                planar.Normalize();

            bool grounded = IsGrounded;
            if (grounded && verticalVelocity < 0f)
                verticalVelocity = -2f;
            else
                verticalVelocity += gravity * deltaTime;

            Vector3 velocity = planar * Mathf.Max(0f, moveSpeed);
            velocity.y = verticalVelocity;
            characterController.Move(velocity * Mathf.Max(0f, deltaTime));
            if (hasRespawnPosition && transform.position.y < respawnPosition.y - fallResetDistance)
                Respawn();
        }

        public bool Jump()
        {
            if (!IsGrounded || jumpHeight <= 0f || gravity >= 0f)
                return false;
            verticalVelocity = Mathf.Sqrt(jumpHeight * -2f * gravity);
            Debug.Log("[FPS_JUMP] Player jumped from " + transform.position);
            return true;
        }

        public void Look(float yawDelta, float pitchDelta)
        {
            Yaw += yawDelta * lookSensitivity;
            Pitch = Mathf.Clamp(Pitch - pitchDelta * lookSensitivity, -89f, 89f);
            transform.rotation = Quaternion.Euler(0f, Yaw, 0f);
            if (playerCamera != null)
                playerCamera.transform.localRotation = Quaternion.Euler(Pitch, 0f, 0f);
        }

        public void SetView(float yaw, float pitch)
        {
            Yaw = yaw;
            Pitch = Mathf.Clamp(pitch, -89f, 89f);
            transform.rotation = Quaternion.Euler(0f, Yaw, 0f);
            if (playerCamera != null)
                playerCamera.transform.localRotation = Quaternion.Euler(Pitch, 0f, 0f);
        }

        public bool Shoot()
        {
            if (weapon == null || playerCamera == null)
                return false;
            return weapon.FireRay(
                new Ray(playerCamera.transform.position, playerCamera.transform.forward),
                Mathf.Max(1f, shootRange));
        }

        private void Warp(Vector3 position)
        {
            EnsureCharacterController();
            bool wasEnabled = characterController.enabled;
            characterController.enabled = false;
            transform.position = position;
            characterController.enabled = wasEnabled;
            verticalVelocity = 0f;
        }

        private bool HasWalkableGroundBelow(float distance)
        {
            RaycastHit[] hits = Physics.RaycastAll(
                transform.position + Vector3.up * 0.15f,
                Vector3.down,
                Mathf.Max(0.2f, distance + 0.15f),
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore);
            FPSPhysicsOrder.SortHits(hits);
            foreach (RaycastHit hit in hits)
                if (hit.collider != null &&
                    !hit.collider.transform.IsChildOf(transform) &&
                    hit.normal.y >= 0.55f)
                    return true;
            return false;
        }

        private static float NormalizePitch(float value)
        {
            value %= 360f;
            return value > 180f ? value - 360f : value;
        }
    }
}
