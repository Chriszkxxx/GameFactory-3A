using System;
using A3GameRuntime;
using UnityEngine;

namespace FPSExample
{
    [DisallowMultipleComponent]
    public sealed class FPSGameRuntimeAdapter : MonoBehaviour
    {
        [Serializable]
        private struct RuntimeState
        {
            public float player_health;
            public float player_max_health;
            public int player_ammo;
            public int magazine_size;
            public int enemy_count;
            public int enemies_killed;
            public float time_remaining;
            public string game_state;
            public bool reloading;
            public int open_doors;
        }

        [SerializeField] private GameObject playerVisualPrefab;
        [SerializeField] private GameObject enemyPrefab;
        [SerializeField] private GameObject riflePrefab;
        [SerializeField] private Transform[] enemySpawnPoints;
        [SerializeField] private RuntimeAnimatorController playerAnimatorController;
        [SerializeField] private RuntimeAnimatorController enemyAnimatorController;
        [SerializeField] private Vector3 initialViewRotation = new Vector3(-13.25f, -75.202f, 0f);
        [SerializeField] private bool captureCursor = true;

        private FPSGameState gameState;
        private FPSWeapon weapon;
        private FPSPlayerController player;
        private FPSEnemySpawner spawner;
        private Camera playerCamera;
        private Animator playerAnimator;
        private GameObject playerGunView;
        private FPSDoor[] doors = Array.Empty<FPSDoor>();

        public float PlayerHealth => gameState != null ? gameState.PlayerHealth : 0f;
        public float PlayerMaxHealth => gameState != null ? gameState.MaxPlayerHealth : 0f;
        public int PlayerAmmo => weapon != null ? weapon.AmmoInMagazine : 0;
        public int MagazineSize => weapon != null ? weapon.MagazineSize : FPSWeapon.DefaultMagazineSize;
        public int EnemyCount => spawner != null ? spawner.AliveCount : 0;
        public int EnemiesKilled => gameState != null ? gameState.EnemiesKilled : 0;
        public float TimeRemaining => gameState != null ? gameState.TimeRemaining : 0f;
        public FPSGameStatus GameStatus => gameState != null ? gameState.Status : FPSGameStatus.Playing;
        public bool IsReloading => weapon != null && weapon.IsReloading;
        public bool IsReady { get; private set; }

        public event Action<float> OnPlayerDamaged;
        public event Action OnEnemySpawned;
        public event Action OnEnemyKilled;
        public event Action OnWeaponFired;
        public event Action OnWeaponReload;
        public event Action OnWeaponReloadComplete;
        public event Action OnEnemyHit;
        public event Action OnGameWin;
        public event Action OnGameLose;
        public event Action OnStateChanged;

        public void ConfigureAssets(
            GameObject playerVisual,
            GameObject enemy,
            GameObject rifle,
            Transform[] spawnPoints,
            RuntimeAnimatorController playerAnimations,
            RuntimeAnimatorController enemyAnimations)
        {
            playerVisualPrefab = playerVisual;
            enemyPrefab = enemy;
            riflePrefab = rifle;
            enemySpawnPoints = spawnPoints;
            playerAnimatorController = playerAnimations;
            enemyAnimatorController = enemyAnimations;
        }

        public void ConfigureView(Vector3 eulerAngles)
        {
            initialViewRotation = eulerAngles;
        }

        private void Start()
        {
            Setup();
        }

        private void OnEnable()
        {
            if (Application.isPlaying)
                CreateEnvironmentColliders();
        }

        public void Setup()
        {
            if (IsReady) return;

            gameState = gameObject.AddComponent<FPSGameState>();
            CreateEnvironmentColliders();
            CreateEnvironmentDoors();
            CreateSafetyBounds();
            GameObject playerObject = new GameObject("FPS_Player");
            playerObject.transform.SetParent(transform, false);
            playerObject.transform.localPosition = Vector3.up * 0.1f;
            weapon = playerObject.AddComponent<FPSWeapon>();
            player = playerObject.AddComponent<FPSPlayerController>();

            GameObject cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            cameraObject.transform.SetParent(playerObject.transform, false);
            cameraObject.transform.localPosition = Vector3.up * FPSPlayerController.DefaultEyeHeight;
            playerCamera = cameraObject.AddComponent<Camera>();
            cameraObject.AddComponent<AudioListener>();
            player.Configure(playerCamera, weapon);
            player.SetInitialView(initialViewRotation);
            player.SnapToGround();

            if (playerVisualPrefab != null)
            {
                GameObject visual = Instantiate(playerVisualPrefab, cameraObject.transform);
                visual.name = "Prepared_Player_Arms_ViewModel";
                visual.transform.localPosition = new Vector3(0f, -1.62f, 0.2f);
                visual.transform.localRotation = Quaternion.identity;
                playerAnimator = visual.GetComponentInChildren<Animator>();
                if (playerAnimator != null)
                {
                    playerAnimator.runtimeAnimatorController = playerAnimatorController;
                    playerAnimator.applyRootMotion = false;
                    playerAnimator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                    playerAnimator.Rebind();
                    playerAnimator.Update(0f);
                    playerAnimator.Play("Idle", 0, 0f);
                    Transform head = playerAnimator.GetBoneTransform(HumanBodyBones.Head);
                    if (head != null) head.localScale = Vector3.zero;
                    Debug.Log(
                        "[FPS_ANIMATION] player avatar=" +
                        (playerAnimator.avatar != null ? playerAnimator.avatar.name : "missing") +
                        " valid=" + (playerAnimator.avatar != null && playerAnimator.avatar.isValid) +
                        " human=" + (playerAnimator.avatar != null && playerAnimator.avatar.isHuman));
                }
                AttachPlayerGun(cameraObject.transform);
            }

            GameObject spawnerObject = new GameObject("FPS_EnemySpawner");
            spawnerObject.transform.SetParent(transform, false);
            spawner = spawnerObject.AddComponent<FPSEnemySpawner>();
            spawner.Configure(
                enemyPrefab,
                enemySpawnPoints,
                enemyAnimatorController,
                riflePrefab,
                player.transform);

            WireEvents();
            RegisterRuntimeEntity(playerObject);
            ResetGame();
            IsReady = true;
            if (captureCursor)
            {
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
            }
            PublishState();
        }

        private void CreateSafetyBounds()
        {
            GameObject bounds = new GameObject("FPS_InvisibleSafetyBounds");
            bounds.transform.SetParent(transform, false);
            CreateSafetyCollider(bounds.transform, "SafetyFloor", new Vector3(0f, -12.45f, 0f), new Vector3(80f, 0.5f, 80f));
            CreateSafetyCollider(bounds.transform, "SafetyWallNorth", new Vector3(0f, 5f, 40f), new Vector3(80f, 10f, 1f));
            CreateSafetyCollider(bounds.transform, "SafetyWallSouth", new Vector3(0f, 5f, -40f), new Vector3(80f, 10f, 1f));
            CreateSafetyCollider(bounds.transform, "SafetyWallEast", new Vector3(40f, 5f, 0f), new Vector3(1f, 10f, 80f));
            CreateSafetyCollider(bounds.transform, "SafetyWallWest", new Vector3(-40f, 5f, 0f), new Vector3(1f, 10f, 80f));
            Debug.Log("[FPS_SAFETY] Invisible floor and arena boundary walls enabled");
        }

        private static void CreateEnvironmentColliders()
        {
            int added = 0;
            int removed = 0;
            int skippedUnreadable = 0;
            foreach (MeshFilter filter in FindObjectsOfType<MeshFilter>(true))
            {
                if (filter == null || filter.sharedMesh == null ||
                    filter.GetComponentInParent<FPSEnemy>() != null ||
                    filter.GetComponentInParent<FPSPlayerController>() != null)
                    continue;
                if (IsNonStructuralEnvironmentMesh(filter.transform))
                {
                    foreach (MeshCollider existingCollider in filter.GetComponents<MeshCollider>())
                    {
                        if (Application.isPlaying)
                            Destroy(existingCollider);
                        else
                            DestroyImmediate(existingCollider);
                        removed++;
                    }
                    continue;
                }
                if (filter.GetComponent<Collider>() != null)
                    continue;
                if (!filter.sharedMesh.isReadable && !Application.isEditor)
                {
                    skippedUnreadable++;
                    continue;
                }
                MeshCollider generatedCollider = filter.gameObject.AddComponent<MeshCollider>();
                generatedCollider.sharedMesh = filter.sharedMesh;
                added++;
            }
            Debug.Log(
                "[FPS_COLLISION] Added " + added +
                " structural colliders; removed " + removed +
                " non-structural mesh colliders; skipped " + skippedUnreadable +
                " unreadable runtime meshes");
        }

        private static bool IsNonStructuralEnvironmentMesh(Transform item)
        {
            string[] names =
            {
                "bed", "mug", "shelf", "crate", "tablet", "cargo",
                "debris", "solar", "lamp", "antenna", "plant",
            };
            for (Transform current = item; current != null; current = current.parent)
            {
                string normalized = current.name.ToLowerInvariant();
                foreach (string name in names)
                    if (normalized.Contains(name))
                        return true;
            }
            return false;
        }

        private static void CreateSafetyCollider(
            Transform parent,
            string name,
            Vector3 center,
            Vector3 size)
        {
            GameObject item = new GameObject(name);
            item.layer = LayerMask.NameToLayer("Ignore Raycast");
            item.transform.SetParent(parent, false);
            item.transform.localPosition = center;
            BoxCollider collider = item.AddComponent<BoxCollider>();
            collider.size = size;
        }

        private void CreateEnvironmentDoors()
        {
            var configured = new System.Collections.Generic.List<FPSDoor>();
            var roots = new System.Collections.Generic.HashSet<int>();
            foreach (Transform candidate in FindObjectsOfType<Transform>(true))
            {
                string normalized = candidate.name.ToLowerInvariant();
                if (normalized != "door" && !normalized.StartsWith("door ("))
                    continue;

                Transform root = candidate;
                while (root.parent != null &&
                    root.parent.name.ToLowerInvariant().Contains("door"))
                    root = root.parent;
                if (!roots.Add(root.GetInstanceID()))
                    continue;

                FPSDoor door = root.GetComponent<FPSDoor>();
                if (door == null)
                    door = root.gameObject.AddComponent<FPSDoor>();
                if (!door.ConfigureFromPrefab())
                    continue;
                door.StateChanged += changed => PublishState();
                configured.Add(door);
            }
            doors = configured.ToArray();
            Debug.Log("[FPS_DOOR] Configured " + doors.Length + " interactive doors");
        }

        private void RegisterRuntimeEntity(GameObject playerObject)
        {
            A3GameRuntimeSubsystem runtime = A3GameRuntimeSubsystem.Instance;
            string worldId = runtime != null ? runtime.worldId : "fps_arena";
            A3GameRuntimeEntityComponent entity = playerObject.AddComponent<A3GameRuntimeEntityComponent>();
            entity.Initialize("fps_player", worldId);
            entity.RuntimeInput += input =>
            {
                player.SetView(input.yaw, input.pitch);
                if (input.jump) player.Jump();
                player.Move(
                    new Vector2(input.move_x, input.move_y),
                    1f / 60f);
            };
        }

        private void WireEvents()
        {
            gameState.PlayerDamaged += amount => { OnPlayerDamaged?.Invoke(amount); PublishState(); };
            gameState.EnemyKilled += () => { OnEnemyKilled?.Invoke(); PublishState(); };
            gameState.GameWon += () => { OnGameWin?.Invoke(); PublishState(); };
            gameState.GameLost += () => { OnGameLose?.Invoke(); PublishState(); };
            gameState.StateChanged += PublishState;
            weapon.WeaponFired += () => { OnWeaponFired?.Invoke(); PublishState(); };
            weapon.EnemyHit += enemy => { OnEnemyHit?.Invoke(); PublishState(); };
            weapon.ReloadStarted += () => { OnWeaponReload?.Invoke(); PublishState(); };
            weapon.ReloadCompleted += () => { OnWeaponReloadComplete?.Invoke(); PublishState(); };
            weapon.StateChanged += PublishState;
            spawner.EnemySpawned += enemy => { OnEnemySpawned?.Invoke(); PublishState(); };
            spawner.EnemyKilled += enemy => gameState.RegisterEnemyKill();
        }

        public bool Shoot()
        {
            bool fired = IsReady && GameStatus == FPSGameStatus.Playing && player.Shoot();
            if (fired && playerAnimator != null) playerAnimator.SetTrigger("Shoot");
            return fired;
        }

        public bool Reload()
        {
            bool started = IsReady && GameStatus == FPSGameStatus.Playing && weapon.StartReload();
            if (started && playerAnimator != null) playerAnimator.SetTrigger("Reload");
            return started;
        }

        public bool Jump()
        {
            return IsReady && GameStatus == FPSGameStatus.Playing && player.Jump();
        }

        public bool Interact()
        {
            if (!IsReady || playerCamera == null)
                return false;

            RaycastHit[] hits = Physics.SphereCastAll(
                playerCamera.transform.position,
                0.25f,
                playerCamera.transform.forward,
                4f,
                Physics.DefaultRaycastLayers,
                QueryTriggerInteraction.Ignore);
            FPSPhysicsOrder.SortHits(hits);
            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null ||
                    hit.collider.transform.IsChildOf(player.transform))
                    continue;
                FPSDoor door = hit.collider.GetComponentInParent<FPSDoor>();
                if (door == null)
                    continue;
                door.Toggle();
                return true;
            }
            FPSDoor nearby = FindClosestDoor(4f);
            if (nearby != null)
            {
                nearby.Toggle();
                return true;
            }
            return false;
        }

        private FPSDoor FindClosestDoor(float maxDistance)
        {
            Vector3 origin = playerCamera.transform.position;
            FPSDoor closest = null;
            float closestDistance = maxDistance * maxDistance;
            foreach (FPSDoor door in doors)
            {
                if (door == null || !door.IsConfigured)
                    continue;
                float distance = (door.transform.position - origin).sqrMagnitude;
                foreach (Collider collider in door.GetComponentsInChildren<Collider>(true))
                {
                    if (collider == null || collider.isTrigger)
                        continue;
                    Vector3 point = collider.bounds.ClosestPoint(origin);
                    distance = Mathf.Min(distance, (point - origin).sqrMagnitude);
                }
                if (distance >= closestDistance)
                    continue;
                closest = door;
                closestDistance = distance;
            }
            return closest;
        }

        public void Move(float moveX, float moveY, float deltaTime)
        {
            if (!IsReady) return;
            player.Move(new Vector2(moveX, moveY), deltaTime);
            if (playerAnimator != null)
                playerAnimator.SetFloat("Speed", new Vector2(moveX, moveY).magnitude);
        }

        public void Look(float yawDelta, float pitchDelta)
        {
            if (IsReady) player.Look(yawDelta, pitchDelta);
        }

        public FPSEnemy SpawnEnemy()
        {
            return IsReady ? spawner.SpawnEnemy() : null;
        }

        public void ResetGame()
        {
            spawner.Clear();
            gameState.ResetState();
            weapon.ResetWeapon();
            player.Respawn();
            foreach (FPSDoor door in doors)
                if (door != null)
                    door.SetOpen(false, true);
            for (int index = 0; index < 3; index++) spawner.SpawnEnemy();
            PublishState();
        }

        public string GetStateJson()
        {
            RuntimeState state = new RuntimeState
            {
                player_health = PlayerHealth,
                player_max_health = PlayerMaxHealth,
                player_ammo = PlayerAmmo,
                magazine_size = MagazineSize,
                enemy_count = EnemyCount,
                enemies_killed = EnemiesKilled,
                time_remaining = TimeRemaining,
                game_state = GameStatus.ToString(),
                reloading = IsReloading,
                open_doors = CountOpenDoors(),
            };
            return JsonUtility.ToJson(state);
        }

        private int CountOpenDoors()
        {
            int count = 0;
            foreach (FPSDoor door in doors)
                if (door != null && door.IsOpen)
                    count++;
            return count;
        }

        private void PublishState()
        {
            OnStateChanged?.Invoke();
            Debug.Log("[FPS_STATE] " + GetStateJson());
        }

        private void Update()
        {
            if (!IsReady) return;
            float deltaTime = Time.deltaTime;
            if (GameStatus == FPSGameStatus.Playing)
            {
                float moveX = Input.GetAxisRaw("Horizontal");
                float moveY = Input.GetAxisRaw("Vertical");
                if (Input.GetKeyDown(KeyCode.Space)) Jump();
                Move(moveX, moveY, deltaTime);
                Look(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y"));
                if (Input.GetMouseButton(0)) Shoot();
                if (Input.GetKeyDown(KeyCode.R)) Reload();
                if (Input.GetKeyDown(KeyCode.E)) Interact();

                gameState.Tick(deltaTime);
                weapon.Tick(deltaTime);
                gameState.DamagePlayer(spawner.Tick(player.transform.position, deltaTime));
            }
            else if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
            {
                ResetGame();
            }
        }

        private void AttachPlayerGun(Transform fallbackParent)
        {
            if (riflePrefab == null) return;
            Transform hand = playerAnimator != null
                ? playerAnimator.GetBoneTransform(HumanBodyBones.RightHand)
                : null;
            Transform parent = hand != null ? hand : fallbackParent;
            playerGunView = Instantiate(riflePrefab);
            playerGunView.name = "Prepared_Gun_FirstPersonView";
            playerGunView.transform.SetParent(parent, false);
            playerGunView.transform.localScale = Vector3.one * 0.42f;
            playerGunView.transform.position =
                parent.position + playerCamera.transform.forward * 0.1f;
            playerGunView.transform.rotation = Quaternion.LookRotation(
                playerCamera.transform.forward,
                playerCamera.transform.up);
            Debug.Log("[FPS_WEAPON] Player gun attached to " + parent.name + " and aimed outward");
        }

        private void LateUpdate()
        {
            if (playerGunView == null || playerCamera == null)
                return;
            playerGunView.transform.rotation = Quaternion.LookRotation(
                playerCamera.transform.forward,
                playerCamera.transform.up);
        }
    }
}
