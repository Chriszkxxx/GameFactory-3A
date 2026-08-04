#pragma once

#include "Common/UdpSocketReceiver.h"
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AAAGameRuntimeInputReceiver.generated.h"

class FJsonObject;
class FSocket;

UCLASS(NotBlueprintable)
class AAAGAMEPLAYABLE_API AAAAGameRuntimeInputReceiver : public AActor
{
    GENERATED_BODY()

public:
    AAAAGameRuntimeInputReceiver();

    virtual void BeginPlay() override;
    virtual void EndPlay(
        const EEndPlayReason::Type EndPlayReason) override;

    bool StartReceiver();
    void StopReceiver();
    bool HandleRuntimeJson(const FString& JsonString);

    UPROPERTY(EditAnywhere, Category = "AAAGame|Runtime")
    int32 ListenPort = 30020;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Runtime")
    bool bAutoStart = true;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Runtime")
    bool bAllowDedicatedServer = true;

private:
    void OnUdpDataReceived(
        const FArrayReaderPtr& Data,
        const FIPv4Endpoint& Endpoint);
    bool DispatchCommand(
        const FString& Type,
        const TSharedPtr<FJsonObject>& Payload);
    bool RegisterParticipant(
        const TSharedPtr<FJsonObject>& Payload);
    bool MarkParticipantOffline(
        const TSharedPtr<FJsonObject>& Payload);
    bool CreateController(
        const TSharedPtr<FJsonObject>& Payload);
    bool BindController(
        const TSharedPtr<FJsonObject>& Payload);
    bool SyncSession(
        const TSharedPtr<FJsonObject>& Payload);
    bool EnsureEntity(
        const TSharedPtr<FJsonObject>& Payload);
    bool ApplyInput(
        const TSharedPtr<FJsonObject>& Payload);
    bool DestroyEntity(
        const TSharedPtr<FJsonObject>& Payload);
    void ResolveRuntimePortFromLaunchOptions();

    FSocket* Socket = nullptr;
    TUniquePtr<FUdpSocketReceiver> SocketReceiver;
};
