#pragma once

#include "Components/AAAGameRuntimeEntityComponent.h"
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/AAAGameControllableEntity.h"
#include "Interfaces/AAAGameEntityFactory.h"
#include "Modules/ModuleManager.h"
#include "Subsystems/WorldSubsystem.h"
#include "FPSExample.generated.h"

class UCameraComponent;
class UStaticMeshComponent;

UCLASS(Blueprintable)
class FPSEXAMPLE_API AAAFPSCharacter
    : public ACharacter
    , public IAAAGameControllableEntity
{
    GENERATED_BODY()

public:
    AAAFPSCharacter();

    virtual void BeginPlay() override;
    virtual float TakeDamage(
        float DamageAmount,
        const FDamageEvent& DamageEvent,
        AController* EventInstigator,
        AActor* DamageCauser) override;

    virtual FString GetRuntimeEntityId_Implementation()
        const override;
    virtual void SetRuntimeEntityId_Implementation(
        const FString& EntityId) override;
    virtual bool ApplyRuntimeInput_Implementation(
        const FAAAGameRuntimeInputState& InputState) override;
    virtual FAAAGameEntitySnapshot
        GetRuntimeSnapshot_Implementation() const override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|FPS")
    void ApplyControlInput(
        float MoveX,
        float MoveY,
        bool bRun,
        bool bJump);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|FPS")
    bool FireWeapon();

    UFUNCTION(BlueprintCallable, Category = "AAAGame|FPS")
    bool ReloadWeapon();

    UFUNCTION(BlueprintCallable, Category = "AAAGame|FPS")
    void ResetCombatant();

    UFUNCTION(BlueprintPure, Category = "AAAGame|FPS")
    float GetHealthPercent() const;

    UFUNCTION(BlueprintPure, Category = "AAAGame|FPS")
    int32 GetMagazineAmmo() const
    {
        return MagazineAmmo;
    }

    UFUNCTION(BlueprintPure, Category = "AAAGame|FPS")
    int32 GetReserveAmmo() const
    {
        return ReserveAmmo;
    }

    UFUNCTION(BlueprintPure, Category = "AAAGame|FPS")
    int32 GetTeamId() const
    {
        return TeamId;
    }

    UFUNCTION(BlueprintCallable, Category = "AAAGame|FPS")
    void SetTeamId(int32 InTeamId)
    {
        TeamId = InTeamId;
    }

private:
    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Runtime")
    TObjectPtr<UAAAGameRuntimeEntityComponent>
        RuntimeEntityComponent;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|FPS")
    TObjectPtr<UCameraComponent> FirstPersonCamera;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|FPS")
    TObjectPtr<UStaticMeshComponent> WeaponMesh;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    float MaxHealth = 100.0f;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|FPS")
    float Health = 100.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    float WalkSpeed = 650.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    float RunSpeed = 1050.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    float WeaponDamage = 24.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    float WeaponRange = 12000.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    int32 MagazineSize = 30;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|FPS")
    int32 MagazineAmmo = 30;

    UPROPERTY(EditAnywhere, Category = "AAAGame|FPS")
    int32 ReserveAmmo = 120;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|FPS")
    int32 TeamId = INDEX_NONE;

    FTransform InitialTransform = FTransform::Identity;
};

UCLASS()
class FPSEXAMPLE_API AAAFPSPlayerController
    : public APlayerController
{
    GENERATED_BODY()

public:
    virtual void PlayerTick(float DeltaTime) override;
    virtual void SetupInputComponent() override;

private:
    void InputTurn(float Value);
    void InputLookUp(float Value);
    void SetForwardPressed();
    void SetForwardReleased();
    void SetBackwardPressed();
    void SetBackwardReleased();
    void SetRightPressed();
    void SetRightReleased();
    void SetLeftPressed();
    void SetLeftReleased();
    void SetRunPressed();
    void SetRunReleased();
    void SetJumpPressed();
    void SetJumpReleased();
    void Fire();
    void Reload();
    void RestartEncounter();

    bool bForwardPressed = false;
    bool bBackwardPressed = false;
    bool bRightPressed = false;
    bool bLeftPressed = false;
    bool bRunPressed = false;
    bool bJumpPressed = false;
};

UCLASS()
class FPSEXAMPLE_API AAAFPSHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};

UCLASS()
class FPSEXAMPLE_API AAAFPSGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAAFPSGameMode();
    virtual void StartPlay() override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|FPS")
    void RestartEncounter();
};

UCLASS()
class FPSEXAMPLE_API UAAAFPSEntityFactory
    : public UObject
    , public IAAAGameEntityFactory
{
    GENERATED_BODY()

public:
    virtual AActor* SpawnRuntimeEntity_Implementation(
        const FAAAGameEntitySpawnRequest& Request) override;
};

UCLASS()
class FPSEXAMPLE_API UAAAFPSRuntimeSubsystem
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
    TObjectPtr<UAAAFPSEntityFactory> EntityFactory;
};

class FFPSExampleModule final : public IModuleInterface
{
};
