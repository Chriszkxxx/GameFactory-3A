using NUnit.Framework;
using UnityEngine;

namespace A3GameRuntime.Tests
{
    public sealed class A3GameRuntimeEntityComponentTests
    {
        [Test]
        public void ApplyInputRecordsAndBroadcastsWithoutOwningMovement()
        {
            var gameObject = new GameObject("RuntimeEntity");
            try
            {
                gameObject.transform.position = new Vector3(2f, 3f, 4f);
                var entity = gameObject.AddComponent<A3GameRuntimeEntityComponent>();
                entity.Initialize("entity", "world");
                int received = 0;
                entity.RuntimeInput += input => received++;

                bool applied = entity.ApplyInput(new A3GameRuntimeInputState
                {
                    move_y = 1f,
                    jump = true,
                    yaw = 90f,
                    ts = 123d,
                });

                Assert.That(applied, Is.True);
                Assert.That(received, Is.EqualTo(1));
                Assert.That(entity.locomotionState, Is.EqualTo(A3GameLocomotionState.Jump));
                Assert.That(entity.motionState, Is.EqualTo("jump"));
                Assert.That(gameObject.transform.position, Is.EqualTo(new Vector3(2f, 3f, 4f)));
                Assert.That(gameObject.transform.eulerAngles, Is.EqualTo(Vector3.zero));
            }
            finally
            {
                Object.DestroyImmediate(gameObject);
            }
        }
    }
}
