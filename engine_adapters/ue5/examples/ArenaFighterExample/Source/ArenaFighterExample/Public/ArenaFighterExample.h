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
#include "ArenaFighterExample.generated.h"

class UCameraComponent;
class USpringArmComponent;

UCLASS(Blueprintable)
class ARENAFIGHTEREXAMPLE_API AAAArenaFighterCharacter
    : public ACharacter
    , public IAAAGameControllableEntity
{
    GENERATED_BODY()

public:
    AAAArenaFighterCharacter();

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

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Arena Fighter")
    void ApplyControlInput(
        float MoveX,
        float MoveY,
        bool bRun,
        bool bJump);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Arena Fighter")
    bool PerformAttack(bool bHeavy);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Arena Fighter")
    void ResetFighter();

    UFUNCTION(BlueprintPure, Category = "AAAGame|Arena Fighter")
    float GetHealthPercent() const;

    UFUNCTION(BlueprintPure, Category = "AAAGame|Arena Fighter")
    bool IsDefeated() const
    {
        return Health <= 0.0f;
    }

    UFUNCTION(BlueprintPure, Category = "AAAGame|Arena Fighter")
    int32 GetTeamId() const
    {
        return TeamId;
    }

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Arena Fighter")
    void SetTeamId(int32 InTeamId)
    {
        TeamId = InTeamId;
    }

private:
    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Runtime")
    TObjectPtr<UAAAGameRuntimeEntityComponent>
        RuntimeEntityComponent;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Arena Fighter")
    float MaxHealth = 100.0f;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Arena Fighter")
    float Health = 100.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Arena Fighter")
    float WalkSpeed = 520.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Arena Fighter")
    float RunSpeed = 850.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Arena Fighter")
    float AttackRange = 220.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Arena Fighter")
    float LightDamage = 18.0f;

    UPROPERTY(EditAnywhere, Category = "AAAGame|Arena Fighter")
    float HeavyDamage = 30.0f;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Arena Fighter")
    int32 TeamId = INDEX_NONE;

    FTransform InitialTransform = FTransform::Identity;
};

UCLASS()
class ARENAFIGHTEREXAMPLE_API AAAArenaFighterPlayerController
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
    void AttackLight();
    void AttackHeavy();
    void RestartArena();

    bool bForwardPressed = false;
    bool bBackwardPressed = false;
    bool bRightPressed = false;
    bool bLeftPressed = false;
    bool bRunPressed = false;
    bool bJumpPressed = false;
};

UCLASS()
class ARENAFIGHTEREXAMPLE_API AAAArenaFighterHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;

private:
    void DrawHealthBar(
        const FString& Label,
        float HealthPercent,
        float X,
        float Y,
        float Width,
        const FLinearColor& Color);
};

UCLASS()
class ARENAFIGHTEREXAMPLE_API AAAArenaFighterGameMode
    : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAAArenaFighterGameMode();
    virtual void StartPlay() override;

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Arena Fighter")
    void RestartArena();
};

UCLASS()
class ARENAFIGHTEREXAMPLE_API UAAArenaFighterEntityFactory
    : public UObject
    , public IAAAGameEntityFactory
{
    GENERATED_BODY()

public:
    virtual AActor* SpawnRuntimeEntity_Implementation(
        const FAAAGameEntitySpawnRequest& Request) override;
};

UCLASS()
class ARENAFIGHTEREXAMPLE_API UAAArenaFighterRuntimeSubsystem
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
    TObjectPtr<UAAArenaFighterEntityFactory> EntityFactory;
};

class FArenaFighterExampleModule final : public IModuleInterface
{
};
