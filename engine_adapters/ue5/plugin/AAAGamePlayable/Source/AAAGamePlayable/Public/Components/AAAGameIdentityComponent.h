#pragma once

#include "Components/ActorComponent.h"
#include "CoreMinimal.h"
#include "AAAGameIdentityComponent.generated.h"

UCLASS(
    BlueprintType,
    Blueprintable,
    ClassGroup = (AAAGame),
    meta = (BlueprintSpawnableComponent))
class AAAGAMEPLAYABLE_API UAAAGameIdentityComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UAAAGameIdentityComponent();

    virtual void GetLifetimeReplicatedProps(
        TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Identity")
    void SetRuntimeIdentity(
        const FString& InParticipantId,
        const FString& InEntityId);

    UPROPERTY(
        Replicated,
        EditAnywhere,
        BlueprintReadOnly,
        Category = "AAAGame|Identity")
    FString ParticipantId;

    UPROPERTY(
        Replicated,
        EditAnywhere,
        BlueprintReadOnly,
        Category = "AAAGame|Identity")
    FString EntityId;
};
