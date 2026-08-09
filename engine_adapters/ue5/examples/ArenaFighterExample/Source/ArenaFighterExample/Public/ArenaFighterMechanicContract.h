#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "ArenaFighterMechanicContract.generated.h"

class AAAArenaFighterCharacter;

UENUM(BlueprintType)
enum class EAAArenaFighterGamePhase : uint8
{
    NotStarted,
    Active,
    Victory,
    Defeat
};

UENUM(BlueprintType)
enum class EAAArenaFighterMechanicEventType : uint8
{
    EncounterStarted,
    HealthChanged,
    AttackPerformed,
    OpponentDefeated,
    PlayerDefeated,
    ArenaRestarted
};

UENUM(BlueprintType)
enum class EAAArenaFighterMechanicCommand : uint8
{
    LightAttack,
    HeavyAttack,
    RestartArena
};

USTRUCT(BlueprintType)
struct ARENAFIGHTEREXAMPLE_API FAAArenaFighterMechanicState
{
    GENERATED_BODY()

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    int32 ContractVersion = 1;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    EAAArenaFighterGamePhase Phase =
        EAAArenaFighterGamePhase::NotStarted;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    float PlayerHealth = 0.0f;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    float PlayerMaxHealth = 0.0f;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    float OpponentHealth = 0.0f;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    float OpponentMaxHealth = 0.0f;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    FString ObjectiveText;
};

USTRUCT(BlueprintType)
struct ARENAFIGHTEREXAMPLE_API FAAArenaFighterMechanicEvent
{
    GENERATED_BODY()

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    int32 ContractVersion = 1;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    EAAArenaFighterMechanicEventType Type =
        EAAArenaFighterMechanicEventType::EncounterStarted;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    FAAArenaFighterMechanicState State;

    UPROPERTY(
        BlueprintReadOnly,
        Category = "A3Game|Arena Fighter|Contract")
    float WorldTimeSeconds = 0.0f;
};

DECLARE_MULTICAST_DELEGATE_OneParam(
    FAAArenaFighterMechanicEventDelegate,
    const FAAArenaFighterMechanicEvent&);

UCLASS()
class ARENAFIGHTEREXAMPLE_API
    UAAArenaFighterMechanicContractSubsystem
    : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(
        const EWorldType::Type WorldType) const override;

    UFUNCTION(
        BlueprintPure,
        Category = "A3Game|Arena Fighter|Contract")
    int32 GetContractVersion() const
    {
        return 1;
    }

    UFUNCTION(
        BlueprintPure,
        Category = "A3Game|Arena Fighter|Contract")
    FAAArenaFighterMechanicState GetMechanicState() const;

    UFUNCTION(
        BlueprintCallable,
        Category = "A3Game|Arena Fighter|Contract")
    bool ExecuteMechanicCommand(
        EAAArenaFighterMechanicCommand Command);

    FAAArenaFighterMechanicEventDelegate& OnMechanicEvent()
    {
        return MechanicEvent;
    }

    void SetPlayer(AAAArenaFighterCharacter* InPlayer);
    void SetEncounterActive(bool bInEncounterActive);
    void PublishEvent(EAAArenaFighterMechanicEventType Type);

private:
    TWeakObjectPtr<AAAArenaFighterCharacter> Player;
    bool bEncounterActive = false;
    FAAArenaFighterMechanicEventDelegate MechanicEvent;
};
