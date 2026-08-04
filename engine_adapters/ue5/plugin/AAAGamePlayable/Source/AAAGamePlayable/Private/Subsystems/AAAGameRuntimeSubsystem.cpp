#include "Subsystems/AAAGameRuntimeSubsystem.h"

#include "Engine/World.h"
#include "EngineUtils.h"
#include "Interfaces/AAAGameEntityFactory.h"
#include "Interfaces/AAAGameRuntimeMessageHandler.h"
#include "Runtime/AAAGameRuntimeInputReceiver.h"
#include "Subsystems/AAAGameWorldSessionSubsystem.h"

bool UAAAGameRuntimeSubsystem::DoesSupportWorldType(
    const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game
        || WorldType == EWorldType::PIE;
}

void UAAAGameRuntimeSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);

    if (!InWorld.IsGameWorld())
    {
        return;
    }
    TActorIterator<AAAAGameRuntimeInputReceiver> ExistingReceiver(
        &InWorld);
    if (ExistingReceiver)
    {
        RuntimeInputReceiver = *ExistingReceiver;
        return;
    }

    FActorSpawnParameters Params;
    Params.Name = TEXT("AAAGame_RuntimeInputReceiver");
    Params.SpawnCollisionHandlingOverride =
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    RuntimeInputReceiver =
        InWorld.SpawnActor<AAAAGameRuntimeInputReceiver>(
            AAAAGameRuntimeInputReceiver::StaticClass(),
            FVector::ZeroVector,
            FRotator::ZeroRotator,
            Params);
}

void UAAAGameRuntimeSubsystem::Deinitialize()
{
    MessageHandlers.Reset();
    RuntimeInputReceiver = nullptr;
    Super::Deinitialize();
}

void UAAAGameRuntimeSubsystem::SetEntityFactory(
    UObject* FactoryObject)
{
    if (UAAAGameWorldSessionSubsystem* Session =
        GetSessionSubsystem())
    {
        Session->SetEntityFactory(FactoryObject);
    }
}

void UAAAGameRuntimeSubsystem::RegisterMessageHandler(
    UObject* HandlerObject)
{
    if (
        !HandlerObject
        || !HandlerObject->GetClass()->ImplementsInterface(
            UAAAGameRuntimeMessageHandler::StaticClass()))
    {
        return;
    }
    MessageHandlers.AddUnique(HandlerObject);
}

void UAAAGameRuntimeSubsystem::UnregisterMessageHandler(
    UObject* HandlerObject)
{
    MessageHandlers.Remove(HandlerObject);
}

UAAAGameWorldSessionSubsystem*
UAAAGameRuntimeSubsystem::GetSessionSubsystem() const
{
    UWorld* World = GetWorld();
    return World
        ? World->GetSubsystem<
            UAAAGameWorldSessionSubsystem>()
        : nullptr;
}

bool UAAAGameRuntimeSubsystem::DispatchExtensionMessage(
    const FString& MessageType,
    const FString& JsonPayload) const
{
    bool bHandled = false;
    for (UObject* Handler : MessageHandlers)
    {
        if (
            !IsValid(Handler)
            || !Handler->GetClass()->ImplementsInterface(
                UAAAGameRuntimeMessageHandler::StaticClass()))
        {
            continue;
        }
        bHandled =
            IAAAGameRuntimeMessageHandler::
                Execute_HandleRuntimeMessage(
                    Handler,
                    MessageType,
                    JsonPayload)
            || bHandled;
    }
    return bHandled;
}
