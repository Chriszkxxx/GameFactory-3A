using System;
using UnityEngine;

namespace FPSExample
{
    public enum FPSGameStatus
    {
        Playing,
        Won,
        Lost
    }

    [DisallowMultipleComponent]
    public sealed class FPSGameState : MonoBehaviour
    {
        public const float DefaultMaxHealth = 100f;
        public const float DefaultSurviveSeconds = 60f;
        public const int DefaultKillTarget = 3;

        [SerializeField] private float maxPlayerHealth = DefaultMaxHealth;
        [SerializeField] private float surviveSeconds = DefaultSurviveSeconds;
        [SerializeField] private int killTarget = DefaultKillTarget;

        public float PlayerHealth { get; private set; }
        public float MaxPlayerHealth => Mathf.Max(1f, maxPlayerHealth);
        public float SurviveSeconds => Mathf.Max(1f, surviveSeconds);
        public float TimeSurvived { get; private set; }
        public float TimeRemaining => Mathf.Max(0f, SurviveSeconds - TimeSurvived);
        public int EnemiesKilled { get; private set; }
        public int KillTarget => Mathf.Max(1, killTarget);
        public FPSGameStatus Status { get; private set; }

        public event Action<float> PlayerDamaged;
        public event Action EnemyKilled;
        public event Action GameWon;
        public event Action GameLost;
        public event Action StateChanged;

        private void Awake()
        {
            ResetState();
        }

        public void ResetState()
        {
            PlayerHealth = MaxPlayerHealth;
            TimeSurvived = 0f;
            EnemiesKilled = 0;
            Status = FPSGameStatus.Playing;
            StateChanged?.Invoke();
        }

        public bool DamagePlayer(float amount)
        {
            if (Status != FPSGameStatus.Playing || amount <= 0f)
                return false;

            float applied = Mathf.Min(PlayerHealth, amount);
            PlayerHealth = Mathf.Max(0f, PlayerHealth - applied);
            PlayerDamaged?.Invoke(applied);
            if (PlayerHealth <= 0f)
            {
                Status = FPSGameStatus.Lost;
                GameLost?.Invoke();
            }
            StateChanged?.Invoke();
            return true;
        }

        public void RegisterEnemyKill()
        {
            if (Status != FPSGameStatus.Playing)
                return;
            EnemiesKilled++;
            EnemyKilled?.Invoke();
            if (EnemiesKilled >= KillTarget)
            {
                Status = FPSGameStatus.Won;
                GameWon?.Invoke();
            }
            StateChanged?.Invoke();
        }

        public void Tick(float deltaTime)
        {
            if (Status != FPSGameStatus.Playing || deltaTime <= 0f)
                return;
            TimeSurvived += deltaTime;
        }
    }
}
