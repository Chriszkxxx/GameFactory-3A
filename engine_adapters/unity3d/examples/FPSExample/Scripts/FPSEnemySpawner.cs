using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace FPSExample
{
    [DisallowMultipleComponent]
    public sealed class FPSEnemySpawner : MonoBehaviour
    {
        [SerializeField] private GameObject enemyPrefab;
        [SerializeField] private Transform[] spawnPoints;
        [SerializeField] private RuntimeAnimatorController animatorController;
        [SerializeField] private GameObject gunPrefab;
        [SerializeField] private Transform playerTarget;

        private readonly List<FPSEnemy> enemies = new List<FPSEnemy>();
        private readonly List<Vector3> usedSpawnPositions = new List<Vector3>();
        private readonly HashSet<int> usedFloorIds = new HashSet<int>();
        private int nextSpawnIndex;

        public IReadOnlyList<FPSEnemy> Enemies => enemies;
        public int AliveCount
        {
            get
            {
                int count = 0;
                foreach (FPSEnemy enemy in enemies)
                    if (enemy != null && !enemy.IsDead) count++;
                return count;
            }
        }

        public event Action<FPSEnemy> EnemySpawned;
        public event Action<FPSEnemy> EnemyKilled;

        public void Configure(
            GameObject prefab,
            Transform[] points,
            RuntimeAnimatorController controller = null,
            GameObject preparedGun = null,
            Transform target = null)
        {
            enemyPrefab = prefab;
            spawnPoints = points;
            animatorController = controller;
            gunPrefab = preparedGun;
            playerTarget = target;
            EnsureSpawnPoints();
        }

        public void EnsureSpawnPoints()
        {
            if (spawnPoints != null && spawnPoints.Length >= 3)
                return;
            spawnPoints = new Transform[3];
            Vector3[] positions =
            {
                new Vector3(-10f, 0f, 16f),
                new Vector3(0f, 0f, 20f),
                new Vector3(10f, 0f, 16f),
            };
            for (int index = 0; index < positions.Length; index++)
            {
                GameObject point = new GameObject("EnemySpawn_" + index);
                point.transform.SetParent(transform, false);
                point.transform.localPosition = positions[index];
                spawnPoints[index] = point.transform;
            }
        }

        public FPSEnemy SpawnEnemy()
        {
            EnsureSpawnPoints();
            Transform point = spawnPoints[nextSpawnIndex % spawnPoints.Length];
            Vector3 spawnPosition = ResolveSpawnPosition(point.position);
            nextSpawnIndex++;
            GameObject instance = enemyPrefab != null
                ? Instantiate(enemyPrefab, spawnPosition, point.rotation)
                : new GameObject("MissingEnemyAsset");
            instance.name = "FPS_Enemy_" + enemies.Count;
            instance.transform.SetPositionAndRotation(spawnPosition, point.rotation);
            FPSEnemy enemy = instance.GetComponent<FPSEnemy>();
            if (enemy == null) enemy = instance.AddComponent<FPSEnemy>();
            enemy.ConfigurePresentation(animatorController, gunPrefab);
            SnapToGround(instance);
            ConfigureCharacterController(instance, enemy);
            enemy.Died += HandleEnemyDied;
            enemies.Add(enemy);
            EnemySpawned?.Invoke(enemy);
            return enemy;
        }

        private void HandleEnemyDied(FPSEnemy enemy)
        {
            EnemyKilled?.Invoke(enemy);
        }

        public float Tick(Vector3 playerPosition, float deltaTime)
        {
            float damage = 0f;
            for (int index = enemies.Count - 1; index >= 0; index--)
            {
                FPSEnemy enemy = enemies[index];
                if (enemy == null)
                {
                    enemies.RemoveAt(index);
                    continue;
                }
                damage += enemy.TickTowards(playerPosition, deltaTime);
                if (enemy.ShouldDestroy)
                {
                    enemies.RemoveAt(index);
                    DestroyEnemyObject(enemy.gameObject);
                }
            }
            return damage;
        }

        public void Clear()
        {
            foreach (FPSEnemy enemy in enemies)
            {
                if (enemy == null) continue;
                enemy.Died -= HandleEnemyDied;
                enemy.gameObject.SetActive(false);
                DestroyEnemyObject(enemy.gameObject);
            }
            enemies.Clear();
            usedSpawnPositions.Clear();
            usedFloorIds.Clear();
            nextSpawnIndex = 0;
        }

        private static void DestroyEnemyObject(GameObject enemyObject)
        {
            if (Application.isPlaying)
                Destroy(enemyObject);
            else
                DestroyImmediate(enemyObject);
        }

        private Vector3 ResolveSpawnPosition(Vector3 requestedPosition)
        {
            if (playerTarget == null)
                return requestedPosition;

            Vector3 playerPosition = playerTarget.position;
            Vector3 best = requestedPosition;
            float bestScore = float.PositiveInfinity;
            float targetDistance = 9f + usedSpawnPositions.Count * 4f;
            foreach (Vector3 sample in CandidateSamples(requestedPosition))
            {
                if (!TryFindWalkableGround(sample, out Vector3 candidate, out Collider ground))
                    continue;
                float distance = Vector2.Distance(
                    new Vector2(candidate.x, candidate.z),
                    new Vector2(playerPosition.x, playerPosition.z));
                if (distance < 8f || distance > 32f)
                    continue;
                if (usedSpawnPositions.Any(used => Vector2.Distance(
                        new Vector2(candidate.x, candidate.z),
                        new Vector2(used.x, used.z)) < 3.25f))
                    continue;
                if (!HasCharacterSpace(candidate, ground))
                    continue;
                float score = Mathf.Abs(distance - targetDistance);
                if (score >= bestScore)
                    continue;
                best = candidate;
                bestScore = score;
            }

            if (bestScore == float.PositiveInfinity)
            {
                Debug.LogWarning(
                    "[FPS_SPAWN] No free walkable sample near configured spawn " +
                    requestedPosition + "; searching player-relative fallback");
                foreach (Vector3 sample in CandidateSamples(playerPosition + Vector3.forward * 14f))
                    if (TryFindWalkableGround(sample, out Vector3 candidate, out Collider ground) &&
                        Vector2.Distance(new Vector2(candidate.x, candidate.z),
                            new Vector2(playerPosition.x, playerPosition.z)) >= 8f &&
                        HasCharacterSpace(candidate, ground))
                    {
                        best = candidate;
                        break;
                    }
            }

            Vector3 resolved = best;
            usedSpawnPositions.Add(resolved);
            Collider resolvedGround = FindGroundAt(resolved);
            if (resolvedGround != null) usedFloorIds.Add(resolvedGround.GetInstanceID());
            Debug.Log(
                "[FPS_SPAWN] Enemy ground=" +
                (resolvedGround != null ? resolvedGround.name : "<none>") +
                " position=" + resolved +
                " player_distance=" + Vector2.Distance(
                    new Vector2(resolved.x, resolved.z),
                    new Vector2(playerPosition.x, playerPosition.z)).ToString("F1"));
            return resolved;
        }

        private static IEnumerable<Vector3> CandidateSamples(Vector3 requested)
        {
            yield return requested;
            float[] rings = { 3f, 6f, 9f };
            foreach (float radius in rings)
                for (int index = 0; index < 8; index++)
                {
                    float angle = index * Mathf.PI * 2f / 8f;
                    yield return requested + new Vector3(
                        Mathf.Cos(angle), 0f, Mathf.Sin(angle)) * radius;
                }
        }

        private static bool TryFindWalkableGround(
            Vector3 sample,
            out Vector3 position,
            out Collider ground)
        {
            position = sample;
            ground = null;
            RaycastHit[] hits = Physics.RaycastAll(
                sample + Vector3.up * 24f,
                Vector3.down,
                48f,
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore);
            Array.Sort(hits, (left, right) => left.distance.CompareTo(right.distance));
            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null || hit.normal.y < 0.55f ||
                    hit.collider.GetComponentInParent<FPSEnemy>() != null ||
                    hit.collider.GetComponentInParent<FPSPlayerController>() != null)
                    continue;
                string name = hit.collider.name.ToLowerInvariant();
                if ((name.Contains("rock") || name.Contains("stone") ||
                     name.Contains("boulder") || name.Contains("crate")) &&
                    hit.point.y > sample.y + 0.5f)
                    continue;
                ground = hit.collider;
                position = new Vector3(sample.x, hit.point.y + 0.03f, sample.z);
                return true;
            }
            return false;
        }

        private static Collider FindGroundAt(Vector3 sample)
        {
            return TryFindWalkableGround(sample, out _, out Collider ground) ? ground : null;
        }

        private static bool HasCharacterSpace(Vector3 feet, Collider ground)
        {
            Vector3 bottom = feet + Vector3.up * 0.45f;
            Vector3 top = feet + Vector3.up * 1.55f;
            foreach (Collider collider in Physics.OverlapCapsule(
                bottom,
                top,
                0.42f,
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore))
            {
                if (collider == null || collider == ground ||
                    collider.GetComponentInParent<FPSEnemySpawner>() != null ||
                    collider.GetComponentInParent<FPSPlayerController>() != null)
                    continue;
                return false;
            }
            return true;
        }

        private static bool IsPreparedFloor(Collider collider)
        {
            if (collider == null || !collider.enabled || collider.isTrigger)
                return false;
            string normalized = collider.name.ToLowerInvariant();
            return normalized.Contains("floor") &&
                !normalized.Contains("safety") &&
                collider.GetComponentInParent<FPSGameRuntimeAdapter>() == null;
        }

        private static void SnapToGround(GameObject target)
        {
            Vector3 referencePosition = target.transform.position;
            RaycastHit[] hits = Physics.RaycastAll(
                referencePosition + Vector3.up * 4f,
                Vector3.down,
                24f,
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore);
            Array.Sort(hits, (left, right) => left.distance.CompareTo(right.distance));
            RaycastHit? terrainFallback = null;
            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null ||
                    hit.collider.transform.IsChildOf(target.transform) ||
                    hit.normal.y < 0.55f ||
                    hit.point.y > referencePosition.y + 0.75f)
                    continue;
                if (hit.collider.GetType().Name == "TerrainCollider")
                {
                    if (!terrainFallback.HasValue) terrainFallback = hit;
                    continue;
                }
                PlaceFeetAtHeight(target, hit.point.y);
                Debug.Log(
                    "[FPS_GROUND] " + target.name + " grounded on " + hit.collider.name +
                    " at " + hit.point + " normal=" + hit.normal);
                return;
            }

            Collider preparedFloor = FindNearestPreparedFloor(referencePosition);
            if (preparedFloor != null)
            {
                Bounds bounds = preparedFloor.bounds;
                target.transform.position = new Vector3(
                    bounds.center.x,
                    target.transform.position.y,
                    bounds.center.z);
                PlaceFeetAtHeight(target, bounds.max.y);
                Debug.Log(
                    "[FPS_GROUND] " + target.name +
                    " moved to nearest prepared floor " + preparedFloor.name +
                    " at " + target.transform.position);
                return;
            }

            if (terrainFallback.HasValue)
            {
                RaycastHit hit = terrainFallback.Value;
                PlaceFeetAtHeight(target, hit.point.y);
                Debug.Log(
                    "[FPS_GROUND] " + target.name + " grounded on terrain collider " +
                    hit.collider.name + " at " + hit.point + " normal=" + hit.normal);
                return;
            }

            Terrain terrain = Terrain.activeTerrain;
            if (terrain != null)
            {
                float terrainY = terrain.SampleHeight(referencePosition) + terrain.transform.position.y;
                PlaceFeetAtHeight(target, terrainY);
                Debug.Log(
                    "[FPS_GROUND] " + target.name +
                    " used Terrain.SampleHeight fallback at y=" + terrainY.ToString("F3"));
            }
        }

        private static Collider FindNearestPreparedFloor(Vector3 referencePosition)
        {
            Collider best = null;
            float bestDistance = float.PositiveInfinity;
            foreach (Collider collider in FindObjectsOfType<Collider>(true))
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

        private static void PlaceFeetAtHeight(GameObject target, float groundY)
        {
            Renderer[] renderers = target.GetComponentsInChildren<Renderer>(true);
            float bottom = float.PositiveInfinity;
            foreach (Renderer renderer in renderers)
                if (renderer != null)
                    bottom = Mathf.Min(bottom, renderer.bounds.min.y);

            float offset = float.IsPositiveInfinity(bottom)
                ? groundY - target.transform.position.y
                : groundY - bottom;
            target.transform.position += Vector3.up * (offset + 0.02f);
        }

        private static void ConfigureCharacterController(
            GameObject target,
            FPSEnemy enemy)
        {
            Renderer[] renderers = target.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0) return;
            Bounds bounds = renderers[0].bounds;
            for (int index = 1; index < renderers.Length; index++)
                bounds.Encapsulate(renderers[index].bounds);

            CharacterController controller = target.GetComponent<CharacterController>();
            if (controller == null) controller = target.AddComponent<CharacterController>();
            Vector3 scale = target.transform.lossyScale;
            float verticalScale = Mathf.Max(0.001f, Mathf.Abs(scale.y));
            float planarScale = Mathf.Max(
                0.001f,
                Mathf.Max(Mathf.Abs(scale.x), Mathf.Abs(scale.z)));
            controller.center = target.transform.InverseTransformPoint(bounds.center);
            controller.radius = Mathf.Clamp(
                Mathf.Min(bounds.size.y * 0.2f, Mathf.Max(bounds.size.x, bounds.size.z) * 0.32f) /
                    planarScale,
                0.25f,
                0.48f);
            controller.height = Mathf.Max(
                bounds.size.y / verticalScale,
                controller.radius * 2f + 0.05f);
            controller.minMoveDistance = 0f;
            enemy.ConfigureCharacterController(controller);
            Debug.Log(
                "[FPS_HITBOX] " + target.name +
                " center=" + controller.center +
                " radius=" + controller.radius.ToString("F2") +
                " height=" + controller.height.ToString("F2"));
        }
    }
}
