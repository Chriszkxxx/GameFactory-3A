#pragma once

#include "Components/AAAGameRuntimeEntityComponent.h"
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/AAAGameControllableEntity.h"
#include "Interfaces/AAAGameEntityFactory.h"
#include "Modules/ModuleManager.h"
#include "Subsystems/WorldSubsystem.h"
#include "RacingExample.generated.h"

class UBoxComponent;
class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;

UCLASS(Blueprintable)
class RACINGEXAMPLE_API AAARacingPawn
    : public APawn
    , public IAAAGameControllableEntity
{
    GENERATED_BODY()

public:
    AAARacingPawn();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    virtual FString GetRuntimeEntityId_Implementation()
        const override;
    virtual void SetRuntimeEntityId_Implementation(
        const FString& EntityId) override;
    virtual bool ApplyRuntimeInput_Implementation(
        const FAAAGameRuntimeInputState& InputState) override;
    virtual FAAAGameEntitySnapshot
        GetRuntimeSnapshot_Implementation() const override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Racing")
    void ApplyDriveInput(
        float Steering,
        float Throttle,
        bool bBoost,
        bool bHandbrake);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Racing")
    void ResetVehicle();

    UFUNCTION(BlueprintPure, Category = "AAAGame|Racing")
    float GetSpeedKph() const;

    UFUNCTION(BlueprintPure, Category = "AAAGame|Racing")
    float GetNitroPercent() const;

    UFUNCTION(BlueprintPure, Category = "AAAGame|Racing")
    bool IsBoosting() const
    {
        return bBoostActive;
    }

    UFUNCTION(BlueprintPure, Category = "AAAGame|Racing")
    bool IsHandbraking() const
    {
        return bHandbrakeActive;
    }

private:
    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Runtime")
    TObjectPtr<UAAAGameRuntimeEntityComponent>
        RuntimeEntityComponent;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Racing")
    TObjectPtr<UBoxComponent> CollisionBox;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Racing")
    TObjectPtr<UStaticMeshComponent> VehicleMesh;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float MaxSpeed = 2400.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float ReverseSpeed = 800.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float Acceleration = 1800.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float Braking = 2800.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float TurnRate = 105.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float BoostMultiplier = 1.45f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float NitroCapacity = 100.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float NitroBurnRate = 32.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Racing")
    float NitroRechargeRate = 14.0f;

    float CurrentSpeed = 0.0f;
    float PendingSteering = 0.0f;
    float PendingThrottle = 0.0f;
    float NitroAmount = 100.0f;
    float LastInputTimeSeconds = -1000.0f;
    bool bPendingBoost = false;
    bool bPendingHandbrake = false;
    bool bBoostActive = false;
    bool bHandbrakeActive = false;
    FTransform InitialTransform = FTransform::Identity;
};

UCLASS()
class RACINGEXAMPLE_API AAARacingPlayerController
    : public APlayerController
{
    GENERATED_BODY()

public:
    virtual void PlayerTick(float DeltaTime) override;
    virtual void SetupInputComponent() override;

private:
    void SetForwardPressed();
    void SetForwardReleased();
    void SetBackwardPressed();
    void SetBackwardReleased();
    void SetRightPressed();
    void SetRightReleased();
    void SetLeftPressed();
    void SetLeftReleased();
    void SetBoostPressed();
    void SetBoostReleased();
    void SetHandbrakePressed();
    void SetHandbrakeReleased();
    void ResetVehicle();

    bool bForwardPressed = false;
    bool bBackwardPressed = false;
    bool bRightPressed = false;
    bool bLeftPressed = false;
    bool bBoostPressed = false;
    bool bHandbrakePressed = false;
};

UCLASS()
class RACINGEXAMPLE_API AAARacingHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};

UCLASS()
class RACINGEXAMPLE_API AAARacingGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAARacingGameMode();
};

UCLASS()
class RACINGEXAMPLE_API UAAARacingEntityFactory
    : public UObject
    , public IAAAGameEntityFactory
{
    GENERATED_BODY()

public:
    virtual AActor* SpawnRuntimeEntity_Implementation(
        const FAAAGameEntitySpawnRequest& Request) override;
};

UCLASS()
class RACINGEXAMPLE_API UAAARacingRuntimeSubsystem
    : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(
        const EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

private:
    UPROPERTY()
    TObjectPtr<UAAARacingEntityFactory> EntityFactory;
};

class FRacingExampleModule final : public IModuleInterface
{
};
