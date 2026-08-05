#pragma once

#include "Components/A3GameRuntimeEntityComponent.h"
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "Interfaces/A3GameControllableEntity.h"
#include "Interfaces/A3GameEntityFactory.h"
#include "Modules/ModuleManager.h"
#include "Subsystems/WorldSubsystem.h"
#include "FPSExample.generated.h"

class UCameraComponent;
class UStaticMeshComponent;

UCLASS(Blueprintable)
class FPSEXAMPLE_API AAAFPSCharacter
    : public ACharacter
    , public IA3GameControllableEntity
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
        const FA3GameRuntimeInputState& InputState) override;
    virtual FA3GameEntitySnapshot
        GetRuntimeSnapshot_Implementation() const override;

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS")
    void ApplyControlInput(
        float MoveX,
        float MoveY,
        bool bRun,
        bool bJump);

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS")
    bool FireWeapon();

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS")
    bool ReloadWeapon();

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS")
    void ResetCombatant();

    UFUNCTION(BlueprintPure, Category = "A3Game|FPS")
    float GetHealthPercent() const;

    UFUNCTION(BlueprintPure, Category = "A3Game|FPS")
    int32 GetMagazineAmmo() const
    {
        return MagazineAmmo;
    }

    UFUNCTION(BlueprintPure, Category = "A3Game|FPS")
    int32 GetReserveAmmo() const
    {
        return ReserveAmmo;
    }

    UFUNCTION(BlueprintPure, Category = "A3Game|FPS")
    int32 GetTeamId() const
    {
        return TeamId;
    }

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS")
    void SetTeamId(int32 InTeamId)
    {
        TeamId = InTeamId;
    }

private:
    UPROPERTY(VisibleAnywhere, Category = "A3Game|Runtime")
    TObjectPtr<UA3GameRuntimeEntityComponent>
        RuntimeEntityComponent;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|FPS")
    TObjectPtr<UCameraComponent> FirstPersonCamera;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|FPS")
    TObjectPtr<UStaticMeshComponent> WeaponMesh;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    float MaxHealth = 100.0f;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|FPS")
    float Health = 100.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    float WalkSpeed = 650.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    float RunSpeed = 1050.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    float WeaponDamage = 24.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    float WeaponRange = 12000.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    int32 MagazineSize = 30;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|FPS")
    int32 MagazineAmmo = 30;

    UPROPERTY(EditAnywhere, Category = "A3Game|FPS")
    int32 ReserveAmmo = 120;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|FPS")
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

    UFUNCTION(BlueprintCallable, Category = "A3Game|FPS")
    void RestartEncounter();
};

UCLASS()
class FPSEXAMPLE_API UAAAFPSEntityFactory
    : public UObject
    , public IA3GameEntityFactory
{
    GENERATED_BODY()

public:
    virtual AActor* SpawnRuntimeEntity_Implementation(
        const FA3GameEntitySpawnRequest& Request) override;
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
