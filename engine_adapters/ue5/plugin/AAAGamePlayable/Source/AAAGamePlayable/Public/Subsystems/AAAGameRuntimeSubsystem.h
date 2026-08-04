#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AAAGameRuntimeSubsystem.generated.h"

class AAAAGameRuntimeInputReceiver;
class UAAAGameWorldSessionSubsystem;

UCLASS()
class AAAGAMEPLAYABLE_API UAAAGameRuntimeSubsystem
    : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(
        const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    void SetEntityFactory(UObject* FactoryObject);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    void RegisterMessageHandler(UObject* HandlerObject);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    void UnregisterMessageHandler(UObject* HandlerObject);

    UFUNCTION(BlueprintPure, Category = "AAAGame|Runtime")
    UAAAGameWorldSessionSubsystem* GetSessionSubsystem() const;

    bool DispatchExtensionMessage(
        const FString& MessageType,
        const FString& JsonPayload) const;

private:
    UPROPERTY()
    TObjectPtr<AAAAGameRuntimeInputReceiver> RuntimeInputReceiver;

    UPROPERTY()
    TArray<TObjectPtr<UObject>> MessageHandlers;
};
