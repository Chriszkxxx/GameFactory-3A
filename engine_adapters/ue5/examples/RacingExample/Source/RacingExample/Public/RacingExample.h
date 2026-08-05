#pragma once

#include "Components/A3GameRuntimeEntityComponent.h"
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/A3GameControllableEntity.h"
#include "Interfaces/A3GameEntityFactory.h"
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
    , public IA3GameControllableEntity
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
        const FA3GameRuntimeInputState& InputState) override;
    virtual FA3GameEntitySnapshot
        GetRuntimeSnapshot_Implementation() const override;

    UFUNCTION(BlueprintCallable, Category = "A3Game|Racing")
    void ApplyDriveInput(
        float Steering,
        float Throttle,
        bool bBoost,
        bool bHandbrake);

    UFUNCTION(BlueprintCallable, Category = "A3Game|Racing")
    void ResetVehicle();

    UFUNCTION(BlueprintPure, Category = "A3Game|Racing")
    float GetSpeedKph() const;

    UFUNCTION(BlueprintPure, Category = "A3Game|Racing")
    float GetNitroPercent() const;

    UFUNCTION(BlueprintPure, Category = "A3Game|Racing")
    bool IsBoosting() const
    {
        return bBoostActive;
    }

    UFUNCTION(BlueprintPure, Category = "A3Game|Racing")
    bool IsHandbraking() const
    {
        return bHandbrakeActive;
    }

private:
    UPROPERTY(VisibleAnywhere, Category = "A3Game|Runtime")
    TObjectPtr<UA3GameRuntimeEntityComponent>
        RuntimeEntityComponent;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Racing")
    TObjectPtr<UBoxComponent> CollisionBox;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Racing")
    TObjectPtr<UStaticMeshComponent> VehicleMesh;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float MaxSpeed = 2400.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float ReverseSpeed = 800.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float Acceleration = 1800.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float Braking = 2800.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float TurnRate = 105.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float BoostMultiplier = 1.45f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float NitroCapacity = 100.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
    float NitroBurnRate = 32.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Racing")
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
    , public IA3GameEntityFactory
{
    GENERATED_BODY()

public:
    virtual AActor* SpawnRuntimeEntity_Implementation(
        const FA3GameEntitySpawnRequest& Request) override;
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
