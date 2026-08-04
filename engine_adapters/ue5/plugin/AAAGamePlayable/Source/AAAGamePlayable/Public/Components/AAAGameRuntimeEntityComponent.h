#pragma once

#include "Components/ActorComponent.h"
#include "CoreMinimal.h"
#include "DataTypes/AAAGameRuntimeTypes.h"
#include "AAAGameRuntimeEntityComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
    FAAAGameRuntimeInputDelegate,
    const FAAAGameRuntimeInputState&,
    InputState);

UCLASS(
    BlueprintType,
    Blueprintable,
    ClassGroup = (AAAGame),
    meta = (BlueprintSpawnableComponent))
class AAAGAMEPLAYABLE_API UAAAGameRuntimeEntityComponent
    : public UActorComponent
{
    GENERATED_BODY()

public:
    UAAAGameRuntimeEntityComponent();

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    void SetRuntimeEntityId(const FString& InEntityId);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Runtime")
    bool ApplyRuntimeInput(
        const FAAAGameRuntimeInputState& InputState);

    UFUNCTION(BlueprintPure, Category = "AAAGame|Runtime")
    FAAAGameEntitySnapshot GetRuntimeSnapshot() const;

    UPROPERTY(
        EditAnywhere,
        BlueprintReadOnly,
        Category = "AAAGame|Runtime")
    FString EntityId;

    UPROPERTY(
        EditAnywhere,
        BlueprintReadWrite,
        Category = "AAAGame|Runtime")
    bool bPersistent = true;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "AAAGame|Runtime")
    EAAAGameLocomotionState LocomotionState =
        EAAAGameLocomotionState::Idle;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "AAAGame|Runtime")
    FString MotionState = TEXT("idle");

    UPROPERTY(
        BlueprintAssignable,
        Category = "AAAGame|Runtime")
    FAAAGameRuntimeInputDelegate OnRuntimeInput;

private:
    double LastInputTimeSeconds = 0.0;
};
