using UnityEngine;

namespace RacingExample
{
    /// <summary>
    /// Arcade vehicle controller with speed, acceleration, braking, steering,
    /// and lap tracking. <see cref="CurrentLap"/> delegates to a
    /// <see cref="RacingLapCounter"/> when assigned, defaulting to 1.
    /// </summary>
    [AddComponentMenu("AAAGameForge/Racing Vehicle Controller")]
    [DisallowMultipleComponent]
    public class RacingVehicleController : MonoBehaviour
    {
        [Header("Physics")]
        [SerializeField] private float maxSpeed = 80f;
        [SerializeField] private float acceleration = 20f;
        [SerializeField] private float brakeDeceleration = 40f;
        [SerializeField] private float turnSpeed = 90f;

        [Header("Lap Tracking")]
        [SerializeField] private RacingLapCounter lapCounter;

        /// <summary>Current speed in units per second.</summary>
        public float Speed { get; private set; }

        /// <summary>Maximum forward speed.</summary>
        public float MaxSpeed => maxSpeed;

        /// <summary>Whether the vehicle is moving.</summary>
        public bool IsMoving => Mathf.Abs(Speed) > 0.1f;

        /// <summary>
        /// Current lap number. Returns the lap counter's value when assigned,
        /// otherwise defaults to 1.
        /// </summary>
        public int CurrentLap =>
            lapCounter != null ? lapCounter.CurrentLap : 1;

        /// <summary>Lap counter reference.</summary>
        public RacingLapCounter LapCounter
        {
            get => lapCounter;
            set => lapCounter = value;
        }

        /// <summary>
        /// Accelerate forward by deltaTime. Increases speed up to MaxSpeed.
        /// </summary>
        public void Accelerate(float deltaTime)
        {
            Speed = Mathf.Min(Speed + acceleration * deltaTime, maxSpeed);
            ApplyMovement(deltaTime);
        }

        /// <summary>
        /// Brake or reverse. Decreases speed down to negative MaxSpeed / 2.
        /// </summary>
        public void Brake(float deltaTime)
        {
            Speed = Mathf.Max(Speed - brakeDeceleration * deltaTime, -maxSpeed * 0.5f);
            ApplyMovement(deltaTime);
        }

        /// <summary>
        /// Steer left (negative) or right (positive). Only effective when the
        /// vehicle is moving. Steering is reversed when going backwards.
        /// </summary>
        public void Steer(float steerInput, float deltaTime)
        {
            if (Mathf.Abs(Speed) < 0.1f)
                return;

            float steerAmount = steerInput * turnSpeed * deltaTime;
            if (Speed < 0f)
                steerAmount = -steerAmount; // reverse steering when going backwards
            transform.Rotate(0f, steerAmount, 0f);
        }

        /// <summary>
        /// Apply natural drag and movement when no throttle/brake input is
        /// given. Gradually reduces speed to zero.
        /// </summary>
        public void Coast(float deltaTime)
        {
            float friction = brakeDeceleration * 0.3f * deltaTime;
            if (Speed > 0f)
                Speed = Mathf.Max(0f, Speed - friction);
            else if (Speed < 0f)
                Speed = Mathf.Min(0f, Speed + friction);

            ApplyMovement(deltaTime);
        }

        private void ApplyMovement(float deltaTime)
        {
            transform.position += transform.forward * Speed * deltaTime;
        }

        /// <summary>Reset the vehicle to a stopped state.</summary>
        public void ResetVehicle()
        {
            Speed = 0f;
        }
    }
}
