#include "Components/AAAGameRuntimeEntityComponent.h"

#include "GameFramework/Actor.h"

UAAAGameRuntimeEntityComponent::UAAAGameRuntimeEntityComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UAAAGameRuntimeEntityComponent::SetRuntimeEntityId(
    const FString& InEntityId)
{
    EntityId = InEntityId;
}

bool UAAAGameRuntimeEntityComponent::ApplyRuntimeInput(
    const FAAAGameRuntimeInputState& InputState)
{
    const bool bMoving =
        !FMath::IsNearlyZero(InputState.MoveX)
        || !FMath::IsNearlyZero(InputState.MoveY);
    if (InputState.bJump)
    {
        LocomotionState = EAAAGameLocomotionState::Jump;
        MotionState = TEXT("jump");
    }
    else if (bMoving && InputState.bRun)
    {
        LocomotionState = EAAAGameLocomotionState::Run;
        MotionState = TEXT("run");
    }
    else if (bMoving)
    {
        LocomotionState = EAAAGameLocomotionState::Walk;
        MotionState = TEXT("walk");
    }
    else
    {
        LocomotionState = EAAAGameLocomotionState::Idle;
        MotionState = TEXT("idle");
    }
    LastInputTimeSeconds = InputState.TimestampSeconds;
    OnRuntimeInput.Broadcast(InputState);
    return true;
}

FAAAGameEntitySnapshot
UAAAGameRuntimeEntityComponent::GetRuntimeSnapshot() const
{
    FAAAGameEntitySnapshot Snapshot;
    Snapshot.EntityId = EntityId;
    Snapshot.bPersistent = bPersistent;
    Snapshot.LocomotionState = LocomotionState;
    Snapshot.MotionState = MotionState;
    Snapshot.LastInputTimeSeconds = LastInputTimeSeconds;

    const AActor* Owner = GetOwner();
    if (Owner)
    {
        Snapshot.ActorLabel = Owner->GetName();
        Snapshot.Position = Owner->GetActorLocation();
        Snapshot.Rotation = Owner->GetActorRotation();
    }
    return Snapshot;
}
