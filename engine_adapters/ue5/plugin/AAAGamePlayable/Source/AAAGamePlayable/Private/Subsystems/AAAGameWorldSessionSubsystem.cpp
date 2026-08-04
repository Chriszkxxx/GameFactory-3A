#include "Subsystems/AAAGameWorldSessionSubsystem.h"

#include "Components/AAAGameRuntimeEntityComponent.h"
#include "GameFramework/Actor.h"
#include "Interfaces/AAAGameControllableEntity.h"
#include "Interfaces/AAAGameEntityFactory.h"

void UAAAGameWorldSessionSubsystem::Tick(float DeltaTime)
{
    const float ConsumeInterval =
        InputConsumeHz > 0.0f
        ? 1.0f / InputConsumeHz
        : 0.05f;
    InputConsumeAccumulator += DeltaTime;
    if (InputConsumeAccumulator >= ConsumeInterval)
    {
        InputConsumeAccumulator = 0.0f;
        ConsumeLatestInputs();
    }
}

TStatId UAAAGameWorldSessionSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(
        UAAAGameWorldSessionSubsystem,
        STATGROUP_Tickables);
}

bool UAAAGameWorldSessionSubsystem::IsTickable() const
{
    const UWorld* World = GetWorld();
    return World && World->IsGameWorld();
}

void UAAAGameWorldSessionSubsystem::SetEntityFactory(
    UObject* FactoryObject)
{
    EntityFactory =
        FactoryObject
        && FactoryObject->GetClass()->ImplementsInterface(
            UAAAGameEntityFactory::StaticClass())
        ? FactoryObject
        : nullptr;
}

FAAAGameParticipantInfo
UAAAGameWorldSessionSubsystem::RegisterParticipant(
    const FString& ParticipantId,
    const FString& UserId)
{
    const FString ResolvedParticipantId =
        ParticipantId.IsEmpty()
        ? MakeRuntimeId(TEXT("p"))
        : ParticipantId;
    if (FAAAGameParticipantInfo* Existing =
        Participants.Find(ResolvedParticipantId))
    {
        Existing->bOnline = true;
        if (!UserId.IsEmpty())
        {
            Existing->UserId = UserId;
        }
        return *Existing;
    }

    FAAAGameParticipantInfo Participant;
    Participant.ParticipantId = ResolvedParticipantId;
    Participant.WorldId = WorldId;
    Participant.UserId = UserId;
    Participants.Add(ResolvedParticipantId, Participant);
    return Participant;
}

void UAAAGameWorldSessionSubsystem::MarkParticipantOffline(
    const FString& ParticipantId)
{
    if (FAAAGameParticipantInfo* Participant =
        Participants.Find(ParticipantId))
    {
        Participant->bOnline = false;
    }

    for (TPair<FString, FAAAGameControllerState>& Pair : Controllers)
    {
        FAAAGameControllerState& Controller = Pair.Value;
        if (Controller.ParticipantId != ParticipantId)
        {
            continue;
        }
        Controller.bOnline = false;
        if (FAAAGameControlBinding* Binding =
            ControlBindings.Find(Controller.ControllerId))
        {
            Binding->bActive = false;
        }
    }
}

AActor* UAAAGameWorldSessionSubsystem::SpawnEntity(
    const FAAAGameEntitySpawnRequest& Request)
{
    if (
        !EntityFactory
        || !EntityFactory->GetClass()->ImplementsInterface(
            UAAAGameEntityFactory::StaticClass()))
    {
        UE_LOG(
            LogTemp,
            Warning,
            TEXT("[AAAGame] SpawnEntity requires a registered entity factory"));
        return nullptr;
    }

    FAAAGameEntitySpawnRequest ResolvedRequest = Request;
    if (ResolvedRequest.WorldId.IsEmpty())
    {
        ResolvedRequest.WorldId = WorldId;
    }
    if (ResolvedRequest.EntityId.IsEmpty())
    {
        ResolvedRequest.EntityId = MakeRuntimeId(TEXT("ent"));
    }

    AActor* Actor =
        IAAAGameEntityFactory::Execute_SpawnRuntimeEntity(
            EntityFactory,
            ResolvedRequest);
    if (!Actor)
    {
        return nullptr;
    }
    return RegisterEntity(
        ResolvedRequest.EntityId,
        Actor,
        ResolvedRequest.ParticipantId)
        ? Actor
        : nullptr;
}

bool UAAAGameWorldSessionSubsystem::RegisterEntity(
    const FString& EntityId,
    AActor* Actor,
    const FString& ParticipantId)
{
    if (EntityId.IsEmpty() || !IsValid(Actor))
    {
        return false;
    }

    EntityActors.Add(EntityId, Actor);
    if (Actor->GetClass()->ImplementsInterface(
        UAAAGameControllableEntity::StaticClass()))
    {
        IAAAGameControllableEntity::Execute_SetRuntimeEntityId(
            Actor,
            EntityId);
    }
    if (UAAAGameRuntimeEntityComponent* Component =
        Actor->FindComponentByClass<
            UAAAGameRuntimeEntityComponent>())
    {
        Component->SetRuntimeEntityId(EntityId);
    }

    if (!ParticipantId.IsEmpty())
    {
        FAAAGameParticipantInfo Participant =
            RegisterParticipant(ParticipantId, TEXT(""));
        Participant.EntityId = EntityId;
        Participants.Add(Participant.ParticipantId, Participant);
    }
    return true;
}

bool UAAAGameWorldSessionSubsystem::RemoveEntity(
    const FString& EntityId,
    bool bDestroyActor)
{
    TObjectPtr<AActor> Actor;
    if (!EntityActors.RemoveAndCopyValue(EntityId, Actor))
    {
        return true;
    }
    for (TPair<FString, FAAAGameControlBinding>& Pair : ControlBindings)
    {
        if (Pair.Value.EntityId == EntityId)
        {
            Pair.Value.bActive = false;
            LatestInputsByController.Remove(Pair.Key);
        }
    }
    if (bDestroyActor && IsValid(Actor))
    {
        Actor->Destroy();
    }
    return true;
}

FAAAGameControllerState
UAAAGameWorldSessionSubsystem::CreateController(
    const FString& ParticipantId,
    const FString& ControllerId,
    const FString& Kind)
{
    const FAAAGameParticipantInfo Participant =
        RegisterParticipant(ParticipantId, TEXT(""));
    const FString ResolvedControllerId =
        ControllerId.IsEmpty()
        ? MakeRuntimeId(TEXT("ctrl"))
        : ControllerId;

    for (TPair<FString, FAAAGameControllerState>& Pair : Controllers)
    {
        FAAAGameControllerState& Controller = Pair.Value;
        if (
            Controller.ParticipantId == Participant.ParticipantId
            && Controller.ControllerId != ResolvedControllerId)
        {
            Controller.bOnline = false;
            if (FAAAGameControlBinding* Binding =
                ControlBindings.Find(Controller.ControllerId))
            {
                Binding->bActive = false;
            }
        }
    }

    FAAAGameControllerState Controller;
    Controller.ControllerId = ResolvedControllerId;
    Controller.ParticipantId = Participant.ParticipantId;
    Controller.WorldId = WorldId;
    Controller.Kind = Kind.IsEmpty() ? TEXT("human") : Kind;
    Controllers.Add(ResolvedControllerId, Controller);
    return Controller;
}

bool UAAAGameWorldSessionSubsystem::BindControllerToEntity(
    const FString& ControllerId,
    const FString& EntityId,
    EAAAGameControlMode Mode,
    int32 Priority)
{
    if (
        !Controllers.Contains(ControllerId)
        || !EntityActors.Contains(EntityId))
    {
        return false;
    }

    FAAAGameControlBinding Binding;
    Binding.ControllerId = ControllerId;
    Binding.EntityId = EntityId;
    Binding.WorldId = WorldId;
    Binding.Mode = Mode;
    Binding.Priority = Priority;
    Binding.bActive = Mode != EAAAGameControlMode::Observing;
    ControlBindings.Add(ControllerId, Binding);
    return true;
}

bool UAAAGameWorldSessionSubsystem::UnbindController(
    const FString& ControllerId)
{
    FAAAGameControlBinding* Binding =
        ControlBindings.Find(ControllerId);
    if (!Binding)
    {
        return false;
    }
    Binding->bActive = false;
    LatestInputsByController.Remove(ControllerId);
    return true;
}

bool UAAAGameWorldSessionSubsystem::EnqueueInputState(
    const FAAAGameRuntimeInputState& InputState)
{
    FAAAGameControlBinding* Binding =
        ControlBindings.Find(InputState.ControllerId);
    if (!Binding || !Binding->bActive)
    {
        return false;
    }
    if (
        !InputState.EntityId.IsEmpty()
        && InputState.EntityId != Binding->EntityId)
    {
        return false;
    }

    FAAAGameRuntimeInputState Normalized = InputState;
    Normalized.WorldId =
        Normalized.WorldId.IsEmpty()
        ? WorldId
        : Normalized.WorldId;
    Normalized.EntityId = Binding->EntityId;
    Normalized.MoveX = FMath::Clamp(
        Normalized.MoveX,
        -1.0f,
        1.0f);
    Normalized.MoveY = FMath::Clamp(
        Normalized.MoveY,
        -1.0f,
        1.0f);
    if (Normalized.TimestampSeconds <= 0.0 && GetWorld())
    {
        Normalized.TimestampSeconds =
            GetWorld()->GetTimeSeconds();
    }
    LatestInputsByController.Add(
        InputState.ControllerId,
        Normalized);
    return true;
}

TArray<FAAAGameEntitySnapshot>
UAAAGameWorldSessionSubsystem::GetWorldStateSnapshot() const
{
    TArray<FAAAGameEntitySnapshot> Snapshots;
    for (const TPair<FString, TObjectPtr<AActor>>& Pair : EntityActors)
    {
        AActor* Actor = Pair.Value.Get();
        if (!IsValid(Actor))
        {
            continue;
        }

        FAAAGameEntitySnapshot Snapshot;
        if (Actor->GetClass()->ImplementsInterface(
            UAAAGameControllableEntity::StaticClass()))
        {
            Snapshot =
                IAAAGameControllableEntity::Execute_GetRuntimeSnapshot(
                    Actor);
        }
        else if (
            const UAAAGameRuntimeEntityComponent* Component =
                Actor->FindComponentByClass<
                    UAAAGameRuntimeEntityComponent>())
        {
            Snapshot = Component->GetRuntimeSnapshot();
        }
        else
        {
            Snapshot.EntityId = Pair.Key;
            Snapshot.ActorLabel = Actor->GetName();
            Snapshot.Position = Actor->GetActorLocation();
            Snapshot.Rotation = Actor->GetActorRotation();
        }
        if (Snapshot.EntityId.IsEmpty())
        {
            Snapshot.EntityId = Pair.Key;
        }
        Snapshots.Add(Snapshot);
    }
    return Snapshots;
}

AActor* UAAAGameWorldSessionSubsystem::GetActorForEntity(
    const FString& EntityId) const
{
    const TObjectPtr<AActor>* Actor = EntityActors.Find(EntityId);
    return Actor ? Actor->Get() : nullptr;
}

void UAAAGameWorldSessionSubsystem::ConsumeLatestInputs()
{
    TMap<FString, FAAAGameRuntimeInputState> InputsToApply =
        MoveTemp(LatestInputsByController);
    LatestInputsByController.Reset();

    for (const TPair<FString, FAAAGameRuntimeInputState>& Pair
        : InputsToApply)
    {
        const FAAAGameRuntimeInputState& InputState = Pair.Value;
        AActor* Actor = GetActorForEntity(InputState.EntityId);
        if (!IsValid(Actor))
        {
            continue;
        }

        if (Actor->GetClass()->ImplementsInterface(
            UAAAGameControllableEntity::StaticClass()))
        {
            IAAAGameControllableEntity::Execute_ApplyRuntimeInput(
                Actor,
                InputState);
            continue;
        }
        if (UAAAGameRuntimeEntityComponent* Component =
            Actor->FindComponentByClass<
                UAAAGameRuntimeEntityComponent>())
        {
            Component->ApplyRuntimeInput(InputState);
        }
    }
}

FString UAAAGameWorldSessionSubsystem::MakeRuntimeId(
    const FString& Prefix) const
{
    return FString::Printf(
        TEXT("%s_%s"),
        *Prefix,
        *FGuid::NewGuid()
            .ToString(EGuidFormats::Digits)
            .Left(12));
}
