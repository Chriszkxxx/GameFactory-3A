#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "RacingMechanicContract.generated.h"

class AAARacingPawn;

UENUM(BlueprintType)
enum class EAAARacingGamePhase : uint8
{
    NotStarted,
    Driving
};

UENUM(BlueprintType)
enum class EAAARacingMechanicEventType : uint8
{
    DriveStarted,
    BoostStarted,
    BoostStopped,
    HandbrakeStarted,
    HandbrakeStopped,
    VehicleReset
};

UENUM(BlueprintType)
enum class EAAARacingMechanicCommand : uint8
{
    ResetVehicle
};

USTRUCT(BlueprintType)
struct RACINGEXAMPLE_API FAAARacingMechanicState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    int32 ContractVersion = 1;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    EAAARacingGamePhase Phase =
        EAAARacingGamePhase::NotStarted;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    float SpeedKph = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    float NitroPercent = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    bool bBoosting = false;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    bool bHandbraking = false;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    FString ObjectiveText;
};

USTRUCT(BlueprintType)
struct RACINGEXAMPLE_API FAAARacingMechanicEvent
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    int32 ContractVersion = 1;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    EAAARacingMechanicEventType Type =
        EAAARacingMechanicEventType::DriveStarted;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    FAAARacingMechanicState State;

    UPROPERTY(BlueprintReadOnly, Category = "A3Game|Racing|Contract")
    float WorldTimeSeconds = 0.0f;
};

DECLARE_MULTICAST_DELEGATE_OneParam(
    FAAARacingMechanicEventDelegate,
    const FAAARacingMechanicEvent&);

UCLASS()
class RACINGEXAMPLE_API UAAARacingMechanicContractSubsystem
    : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(
        const EWorldType::Type WorldType) const override;

    UFUNCTION(BlueprintPure, Category = "A3Game|Racing|Contract")
    int32 GetContractVersion() const
    {
        return 1;
    }

    UFUNCTION(BlueprintPure, Category = "A3Game|Racing|Contract")
    FAAARacingMechanicState GetMechanicState() const;

    UFUNCTION(BlueprintCallable, Category = "A3Game|Racing|Contract")
    bool ExecuteMechanicCommand(
        EAAARacingMechanicCommand Command);

    FAAARacingMechanicEventDelegate& OnMechanicEvent()
    {
        return MechanicEvent;
    }

    void SetVehicle(AAARacingPawn* InVehicle);
    void SetDriveActive(bool bInDriveActive);
    void PublishEvent(EAAARacingMechanicEventType Type);

private:
    TWeakObjectPtr<AAARacingPawn> Vehicle;
    bool bDriveActive = false;
    FAAARacingMechanicEventDelegate MechanicEvent;
};
