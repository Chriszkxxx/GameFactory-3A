#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "FPSMechanicContract.generated.h"

class AAAFPSCharacter;

UENUM(BlueprintType)
enum class EAAAFPSGamePhase : uint8
{
    NotStarted,
    Active,
    Victory,
    Defeat
};

UENUM(BlueprintType)
enum class EAAAFPSMechanicEventType : uint8
{
    EncounterStarted,
    HealthChanged,
    AmmoChanged,
    TargetDefeated,
    PlayerDefeated,
    EncounterRestarted
};

UENUM(BlueprintType)
enum class EAAAFPSMechanicCommand : uint8
{
    Fire,
    Reload,
    RestartEncounter
};

USTRUCT(BlueprintType)
struct FPSEXAMPLE_API FAAFPSMechanicState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    int32 ContractVersion = 1;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    EAAAFPSGamePhase Phase = EAAAFPSGamePhase::NotStarted;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    float PlayerHealth = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    float PlayerMaxHealth = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    int32 MagazineAmmo = 0;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    int32 ReserveAmmo = 0;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    int32 TargetsRemaining = 0;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    bool bReloading = false;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    FString ObjectiveText;
};

USTRUCT(BlueprintType)
struct FPSEXAMPLE_API FAAFPSMechanicEvent
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    int32 ContractVersion = 1;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    EAAAFPSMechanicEventType Type =
        EAAAFPSMechanicEventType::EncounterStarted;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    FAAFPSMechanicState State;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|FPS|Contract")
    float WorldTimeSeconds = 0.0f;
};

DECLARE_MULTICAST_DELEGATE_OneParam(
    FAAFPSMechanicEventDelegate,
    const FAAFPSMechanicEvent&);

UCLASS()
class FPSEXAMPLE_API UAAAFPSMechanicContractSubsystem
    : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(
        const EWorldType::Type WorldType) const override;

    UFUNCTION(BlueprintPure, Category = "A3Game|FPS|Contract")
    int32 GetContractVersion() const
    {
        return 1;
    }

    UFUNCTION(BlueprintPure, Category = "A3Game|FPS|Contract")
    FAAFPSMechanicState GetMechanicState() const;

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS|Contract")
    bool ExecuteMechanicCommand(EAAAFPSMechanicCommand Command);

    FAAFPSMechanicEventDelegate& OnMechanicEvent()
    {
        return MechanicEvent;
    }

    void SetPlayer(AAAFPSCharacter* InPlayer);
    void SetEncounterActive(bool bInEncounterActive);
    void PublishEvent(EAAAFPSMechanicEventType Type);

private:
    TWeakObjectPtr<AAAFPSCharacter> Player;
    bool bEncounterActive = false;
    FAAFPSMechanicEventDelegate MechanicEvent;
};
