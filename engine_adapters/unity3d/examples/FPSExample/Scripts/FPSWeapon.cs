using System;
using UnityEngine;

namespace FPSExample
{
    [DisallowMultipleComponent]
    public sealed class FPSWeapon : MonoBehaviour
    {
        public const float DefaultDamage = 25f;
        public const float DefaultFireCooldown = 0.25f;
        public const float DefaultReloadTime = 2f;
        public const int DefaultMagazineSize = 30;

        [SerializeField] private float damage = DefaultDamage;
        [SerializeField] private float fireCooldown = DefaultFireCooldown;
        [SerializeField] private float reloadTime = DefaultReloadTime;
        [SerializeField] private int magazineSize = DefaultMagazineSize;

        private float cooldownRemaining;
        private float reloadRemaining;

        public float Damage => Mathf.Max(1f, damage);
        public float FireCooldown => Mathf.Max(0.01f, fireCooldown);
        public float ReloadTime => Mathf.Max(0.01f, reloadTime);
        public int MagazineSize => Mathf.Max(1, magazineSize);
        public int AmmoInMagazine { get; private set; }
        public bool IsReloading { get; private set; }
        public bool CanFire => !IsReloading && cooldownRemaining <= 0f && AmmoInMagazine > 0;

        public event Action WeaponFired;
        public event Action<FPSEnemy> EnemyHit;
        public event Action ReloadStarted;
        public event Action ReloadCompleted;
        public event Action StateChanged;

        private void Awake()
        {
            ResetWeapon();
        }

        public bool FireAt(FPSEnemy target)
        {
            if (!CanFire || target == null || target.IsDead)
                return false;
            CommitShot();
            target.TakeDamage(Damage);
            EnemyHit?.Invoke(target);
            return true;
        }

        public bool FireRay(Ray ray, float range, int layerMask = Physics.DefaultRaycastLayers)
        {
            if (!CanFire)
                return false;
            CommitShot();
            RaycastHit[] hits = Physics.RaycastAll(
                ray,
                range,
                layerMask,
                QueryTriggerInteraction.Ignore);
            Array.Sort(hits, (left, right) => left.distance.CompareTo(right.distance));
            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null || hit.collider.transform.IsChildOf(transform))
                    continue;
                FPSEnemy enemy = hit.collider.GetComponentInParent<FPSEnemy>();
                Debug.Log(
                    "[FPS_HIT] collider=" + hit.collider.name +
                    " enemy=" + (enemy != null ? enemy.name : "none"));
                if (enemy != null && !enemy.IsDead)
                {
                    enemy.TakeDamage(Damage);
                    EnemyHit?.Invoke(enemy);
                    Debug.Log(
                        "[FPS_DAMAGE] enemy=" + enemy.name +
                        " health=" + enemy.Health.ToString("F1") +
                        " dead=" + enemy.IsDead);
                }
                return true;
            }
            Debug.Log("[FPS_HIT] miss");
            return true;
        }

        private void CommitShot()
        {
            AmmoInMagazine--;
            cooldownRemaining = FireCooldown;
            WeaponFired?.Invoke();
            StateChanged?.Invoke();
            if (AmmoInMagazine == 0)
                StartReload();
        }

        public bool StartReload()
        {
            if (IsReloading || AmmoInMagazine >= MagazineSize)
                return false;
            IsReloading = true;
            reloadRemaining = ReloadTime;
            ReloadStarted?.Invoke();
            StateChanged?.Invoke();
            return true;
        }

        public void Tick(float deltaTime)
        {
            if (deltaTime <= 0f)
                return;
            cooldownRemaining = Mathf.Max(0f, cooldownRemaining - deltaTime);
            if (cooldownRemaining <= 0.0001f)
                cooldownRemaining = 0f;
            if (!IsReloading)
                return;
            reloadRemaining -= deltaTime;
            if (reloadRemaining > 0f)
                return;
            IsReloading = false;
            reloadRemaining = 0f;
            AmmoInMagazine = MagazineSize;
            ReloadCompleted?.Invoke();
            StateChanged?.Invoke();
        }

        public void ResetWeapon()
        {
            AmmoInMagazine = MagazineSize;
            cooldownRemaining = 0f;
            reloadRemaining = 0f;
            IsReloading = false;
            StateChanged?.Invoke();
        }
    }
}
