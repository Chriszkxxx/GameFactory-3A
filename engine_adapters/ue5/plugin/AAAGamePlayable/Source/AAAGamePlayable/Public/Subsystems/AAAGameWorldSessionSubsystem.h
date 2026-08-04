#pragma once

#include "CoreMinimal.h"
#include "DataTypes/AAAGameRuntimeTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "AAAGameWorldSessionSubsystem.generated.h"

class AActor;

UCLASS()
class AAAGAMEPLAYABLE_API UAAAGameWorldSessionSubsystem
    : public UTickableWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickable() const override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    void SetEntityFactory(UObject* FactoryObject);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    FAAAGameParticipantInfo RegisterParticipant(
        const FString& ParticipantId,
        const FString& UserId);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    void MarkParticipantOffline(const FString& ParticipantId);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    AActor* SpawnEntity(
        const FAAAGameEntitySpawnRequest& Request);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    bool RegisterEntity(
        const FString& EntityId,
        AActor* Actor,
        const FString& ParticipantId);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    bool RemoveEntity(
        const FString& EntityId,
        bool bDestroyActor);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    FAAAGameControllerState CreateController(
        const FString& ParticipantId,
        const FString& ControllerId,
        const FString& Kind);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    bool BindControllerToEntity(
        const FString& ControllerId,
        const FString& EntityId,
        EAAAGameControlMode Mode,
        int32 Priority);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    bool UnbindController(const FString& ControllerId);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    bool EnqueueInputState(
        const FAAAGameRuntimeInputState& InputState);

    UFUNCTION(BlueprintPure, Category = "AAAGame|Runtime")
    TArray<FAAAGameEntitySnapshot> GetWorldStateSnapshot() const;

    UFUNCTION(BlueprintPure, Category = "AAAGame|Runtime")
    AActor* GetActorForEntity(const FString& EntityId) const;

    UPROPERTY(
        EditAnywhere,
        BlueprintReadWrite,
        Category = "AAAGame|Runtime")
    FString WorldId = TEXT("world_001");

    UPROPERTY(
        EditAnywhere,
        BlueprintReadWrite,
        Category = "AAAGame|Runtime",
        meta = (ClampMin = "1.0"))
    float InputConsumeHz = 20.0f;

private:
    void ConsumeLatestInputs();
    FString MakeRuntimeId(const FString& Prefix) const;

    UPROPERTY()
    TObjectPtr<UObject> EntityFactory;

    UPROPERTY()
    TMap<FString, FAAAGameParticipantInfo> Participants;

    UPROPERTY()
    TMap<FString, FAAAGameControllerState> Controllers;

    UPROPERTY()
    TMap<FString, FAAAGameControlBinding> ControlBindings;

    UPROPERTY()
    TMap<FString, TObjectPtr<AActor>> EntityActors;

    UPROPERTY()
    TMap<FString, FAAAGameRuntimeInputState> LatestInputsByController;

    float InputConsumeAccumulator = 0.0f;
};
