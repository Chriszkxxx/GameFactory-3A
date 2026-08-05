#include "ArenaFighterExample.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Subsystems/A3GameRuntimeSubsystem.h"

IMPLEMENT_MODULE(FArenaFighterExampleModule, ArenaFighterExample)

AAAArenaFighterCharacter::AAAArenaFighterCharacter()
{
    PrimaryActorTick.bCanEverTick = false;

    RuntimeEntityComponent =
        CreateDefaultSubobject<UA3GameRuntimeEntityComponent>(
            TEXT("RuntimeEntity"));

    GetCapsuleComponent()->InitCapsuleSize(42.0f, 88.0f);
    UCharacterMovementComponent* Movement =
        GetCharacterMovement();
    Movement->bOrientRotationToMovement = true;
    Movement->RotationRate = FRotator(0.0f, 540.0f, 0.0f);
    Movement->MaxWalkSpeed = WalkSpeed;

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(
        TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 520.0f;
    CameraBoom->bUsePawnControlRotation = true;
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 12.0f;

    FollowCamera = CreateDefaultSubobject<UCameraComponent>(
        TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(
        CameraBoom,
        USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;
}

void AAAArenaFighterCharacter::BeginPlay()
{
    Super::BeginPlay();
    InitialTransform = GetActorTransform();
    Health = MaxHealth;
}

float AAAArenaFighterCharacter::TakeDamage(
    float DamageAmount,
    const FDamageEvent& DamageEvent,
    AController* EventInstigator,
    AActor* DamageCauser)
{
    const float AppliedDamage = Super::TakeDamage(
        DamageAmount,
        DamageEvent,
        EventInstigator,
        DamageCauser);
    if (AppliedDamage <= 0.0f || IsDefeated())
    {
        return AppliedDamage;
    }

    Health = FMath::Clamp(
        Health - AppliedDamage,
        0.0f,
        MaxHealth);
    if (IsDefeated())
    {
        GetCharacterMovement()->DisableMovement();
    }
    return AppliedDamage;
}

FString AAAArenaFighterCharacter::
GetRuntimeEntityId_Implementation() const
{
    return RuntimeEntityComponent
        ? RuntimeEntityComponent->EntityId
        : FString();
}

void AAAArenaFighterCharacter::
SetRuntimeEntityId_Implementation(const FString& EntityId)
{
    if (RuntimeEntityComponent)
    {
        RuntimeEntityComponent->SetRuntimeEntityId(EntityId);
    }
}

bool AAAArenaFighterCharacter::ApplyRuntimeInput_Implementation(
    const FA3GameRuntimeInputState& InputState)
{
    if (!RuntimeEntityComponent
        || !RuntimeEntityComponent->ApplyRuntimeInput(InputState))
    {
        return false;
    }
    SetActorRotation(FRotator(0.0f, InputState.Yaw, 0.0f));
    ApplyControlInput(
        InputState.MoveX,
        InputState.MoveY,
        InputState.bRun,
        InputState.bJump);
    return true;
}

FA3GameEntitySnapshot AAAArenaFighterCharacter::
GetRuntimeSnapshot_Implementation() const
{
    return RuntimeEntityComponent
        ? RuntimeEntityComponent->GetRuntimeSnapshot()
        : FA3GameEntitySnapshot();
}

void AAAArenaFighterCharacter::ApplyControlInput(
    float MoveX,
    float MoveY,
    bool bRun,
    bool bJump)
{
    if (IsDefeated())
    {
        return;
    }

    UCharacterMovementComponent* Movement =
        GetCharacterMovement();
    Movement->MaxWalkSpeed = bRun ? RunSpeed : WalkSpeed;
    const FRotator ViewRotation = Controller
        ? Controller->GetControlRotation()
        : GetActorRotation();
    const FRotator YawRotation(
        0.0f,
        ViewRotation.Yaw,
        0.0f);
    AddMovementInput(
        FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X),
        FMath::Clamp(MoveY, -1.0f, 1.0f));
    AddMovementInput(
        FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y),
        FMath::Clamp(MoveX, -1.0f, 1.0f));
    if (bJump)
    {
        Jump();
    }
    else
    {
        StopJumping();
    }
}

bool AAAArenaFighterCharacter::PerformAttack(bool bHeavy)
{
    if (IsDefeated())
    {
        return false;
    }

    AAAArenaFighterCharacter* Target = nullptr;
    float BestDistanceSquared = FMath::Square(AttackRange);
    for (TActorIterator<AAAArenaFighterCharacter> It(GetWorld());
        It;
        ++It)
    {
        AAAArenaFighterCharacter* Candidate = *It;
        if (!IsValid(Candidate)
            || Candidate == this
            || Candidate->IsDefeated()
            || Candidate->GetTeamId() == TeamId)
        {
            continue;
        }
        const float DistanceSquared = FVector::DistSquared2D(
            GetActorLocation(),
            Candidate->GetActorLocation());
        if (DistanceSquared <= BestDistanceSquared)
        {
            BestDistanceSquared = DistanceSquared;
            Target = Candidate;
        }
    }
    if (!Target)
    {
        return false;
    }

    UGameplayStatics::ApplyDamage(
        Target,
        bHeavy ? HeavyDamage : LightDamage,
        GetController(),
        this,
        UDamageType::StaticClass());
    return true;
}

void AAAArenaFighterCharacter::ResetFighter()
{
    Health = MaxHealth;
    SetActorTransform(
        InitialTransform,
        false,
        nullptr,
        ETeleportType::TeleportPhysics);
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    GetCharacterMovement()->StopMovementImmediately();
}

float AAAArenaFighterCharacter::GetHealthPercent() const
{
    return MaxHealth > 0.0f
        ? FMath::Clamp(Health / MaxHealth, 0.0f, 1.0f)
        : 0.0f;
}

void AAAArenaFighterPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    if (!InputComponent)
    {
        return;
    }

    InputComponent->BindAxisKey(
        EKeys::MouseX,
        this,
        &AAAArenaFighterPlayerController::InputTurn);
    InputComponent->BindAxisKey(
        EKeys::MouseY,
        this,
        &AAAArenaFighterPlayerController::InputLookUp);
    InputComponent->BindKey(
        EKeys::W,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::SetForwardPressed);
    InputComponent->BindKey(
        EKeys::W,
        IE_Released,
        this,
        &AAAArenaFighterPlayerController::SetForwardReleased);
    InputComponent->BindKey(
        EKeys::S,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::SetBackwardPressed);
    InputComponent->BindKey(
        EKeys::S,
        IE_Released,
        this,
        &AAAArenaFighterPlayerController::SetBackwardReleased);
    InputComponent->BindKey(
        EKeys::D,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::SetRightPressed);
    InputComponent->BindKey(
        EKeys::D,
        IE_Released,
        this,
        &AAAArenaFighterPlayerController::SetRightReleased);
    InputComponent->BindKey(
        EKeys::A,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::SetLeftPressed);
    InputComponent->BindKey(
        EKeys::A,
        IE_Released,
        this,
        &AAAArenaFighterPlayerController::SetLeftReleased);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::SetRunPressed);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Released,
        this,
        &AAAArenaFighterPlayerController::SetRunReleased);
    InputComponent->BindKey(
        EKeys::SpaceBar,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::SetJumpPressed);
    InputComponent->BindKey(
        EKeys::SpaceBar,
        IE_Released,
        this,
        &AAAArenaFighterPlayerController::SetJumpReleased);
    InputComponent->BindKey(
        EKeys::J,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::AttackLight);
    InputComponent->BindKey(
        EKeys::K,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::AttackHeavy);
    InputComponent->BindKey(
        EKeys::R,
        IE_Pressed,
        this,
        &AAAArenaFighterPlayerController::RestartArena);
}

void AAAArenaFighterPlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if (AAAArenaFighterCharacter* Fighter =
        Cast<AAAArenaFighterCharacter>(GetPawn()))
    {
        Fighter->ApplyControlInput(
            (bRightPressed ? 1.0f : 0.0f)
                - (bLeftPressed ? 1.0f : 0.0f),
            (bForwardPressed ? 1.0f : 0.0f)
                - (bBackwardPressed ? 1.0f : 0.0f),
            bRunPressed,
            bJumpPressed);
    }
}

void AAAArenaFighterPlayerController::InputTurn(float Value)
{
    AddYawInput(Value);
}

void AAAArenaFighterPlayerController::InputLookUp(float Value)
{
    AddPitchInput(-Value);
}

void AAAArenaFighterPlayerController::SetForwardPressed()
{
    bForwardPressed = true;
}

void AAAArenaFighterPlayerController::SetForwardReleased()
{
    bForwardPressed = false;
}

void AAAArenaFighterPlayerController::SetBackwardPressed()
{
    bBackwardPressed = true;
}

void AAAArenaFighterPlayerController::SetBackwardReleased()
{
    bBackwardPressed = false;
}

void AAAArenaFighterPlayerController::SetRightPressed()
{
    bRightPressed = true;
}

void AAAArenaFighterPlayerController::SetRightReleased()
{
    bRightPressed = false;
}

void AAAArenaFighterPlayerController::SetLeftPressed()
{
    bLeftPressed = true;
}

void AAAArenaFighterPlayerController::SetLeftReleased()
{
    bLeftPressed = false;
}

void AAAArenaFighterPlayerController::SetRunPressed()
{
    bRunPressed = true;
}

void AAAArenaFighterPlayerController::SetRunReleased()
{
    bRunPressed = false;
}

void AAAArenaFighterPlayerController::SetJumpPressed()
{
    bJumpPressed = true;
}

void AAAArenaFighterPlayerController::SetJumpReleased()
{
    bJumpPressed = false;
}

void AAAArenaFighterPlayerController::AttackLight()
{
    if (AAAArenaFighterCharacter* Fighter =
        Cast<AAAArenaFighterCharacter>(GetPawn()))
    {
        Fighter->PerformAttack(false);
    }
}

void AAAArenaFighterPlayerController::AttackHeavy()
{
    if (AAAArenaFighterCharacter* Fighter =
        Cast<AAAArenaFighterCharacter>(GetPawn()))
    {
        Fighter->PerformAttack(true);
    }
}

void AAAArenaFighterPlayerController::RestartArena()
{
    if (AAAArenaFighterGameMode* GameMode =
        GetWorld()
            ? GetWorld()->GetAuthGameMode<
                AAAArenaFighterGameMode>()
            : nullptr)
    {
        GameMode->RestartArena();
    }
}

void AAAArenaFighterHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas)
    {
        return;
    }

    AAAArenaFighterCharacter* Player =
        Cast<AAAArenaFighterCharacter>(GetOwningPawn());
    if (!Player)
    {
        return;
    }

    AAAArenaFighterCharacter* Opponent = nullptr;
    for (TActorIterator<AAAArenaFighterCharacter> It(GetWorld());
        It;
        ++It)
    {
        if (*It != Player
            && It->GetTeamId() != Player->GetTeamId())
        {
            Opponent = *It;
            break;
        }
    }

    const float Width = FMath::Clamp(
        Canvas->SizeX * 0.32f,
        260.0f,
        520.0f);
    DrawHealthBar(
        TEXT("PLAYER"),
        Player->GetHealthPercent(),
        48.0f,
        48.0f,
        Width,
        FLinearColor(0.1f, 0.75f, 0.3f, 1.0f));
    if (Opponent)
    {
        DrawHealthBar(
            TEXT("OPPONENT"),
            Opponent->GetHealthPercent(),
            Canvas->SizeX - Width - 48.0f,
            48.0f,
            Width,
            FLinearColor(0.9f, 0.18f, 0.12f, 1.0f));
    }
}

void AAAArenaFighterHUD::DrawHealthBar(
    const FString& Label,
    float HealthPercent,
    float X,
    float Y,
    float Width,
    const FLinearColor& Color)
{
    DrawText(
        Label,
        FLinearColor::White,
        X,
        Y - 24.0f,
        GEngine ? GEngine->GetSmallFont() : nullptr);
    DrawRect(
        FLinearColor(0.02f, 0.02f, 0.02f, 0.9f),
        X,
        Y,
        Width,
        24.0f);
    DrawRect(
        Color,
        X + 3.0f,
        Y + 3.0f,
        (Width - 6.0f)
            * FMath::Clamp(HealthPercent, 0.0f, 1.0f),
        18.0f);
}

AAAArenaFighterGameMode::AAAArenaFighterGameMode()
{
    DefaultPawnClass = AAAArenaFighterCharacter::StaticClass();
    PlayerControllerClass =
        AAAArenaFighterPlayerController::StaticClass();
    HUDClass = AAAArenaFighterHUD::StaticClass();
}

void AAAArenaFighterGameMode::StartPlay()
{
    Super::StartPlay();
    AAAArenaFighterCharacter* Player =
        Cast<AAAArenaFighterCharacter>(
            UGameplayStatics::GetPlayerPawn(this, 0));
    if (!Player)
    {
        return;
    }
    Player->SetTeamId(0);

    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride =
        ESpawnActorCollisionHandlingMethod::
            AdjustIfPossibleButAlwaysSpawn;
    AAAArenaFighterCharacter* Opponent =
        GetWorld()->SpawnActor<AAAArenaFighterCharacter>(
            AAAArenaFighterCharacter::StaticClass(),
            Player->GetActorLocation()
                + Player->GetActorForwardVector() * 420.0f,
            (Player->GetActorForwardVector() * -1.0f).Rotation(),
            Params);
    if (Opponent)
    {
        Opponent->SetTeamId(1);
        Opponent->Tags.AddUnique(
            FName(TEXT("A3GameArenaOpponent")));
    }
}

void AAAArenaFighterGameMode::RestartArena()
{
    for (TActorIterator<AAAArenaFighterCharacter> It(GetWorld());
        It;
        ++It)
    {
        It->ResetFighter();
    }
}

AActor* UAAArenaFighterEntityFactory::
SpawnRuntimeEntity_Implementation(
    const FA3GameEntitySpawnRequest& Request)
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }

    AAAArenaFighterCharacter* Fighter =
        World->SpawnActor<AAAArenaFighterCharacter>(
            AAAArenaFighterCharacter::StaticClass(),
            Request.Transform);
    if (!Fighter)
    {
        return nullptr;
    }
    IA3GameControllableEntity::Execute_SetRuntimeEntityId(
        Fighter,
        Request.EntityId);
    if (const FString* TeamValue =
        Request.Parameters.Find(TEXT("team_id")))
    {
        Fighter->SetTeamId(FCString::Atoi(**TeamValue));
    }
    return Fighter;
}

bool UAAArenaFighterRuntimeSubsystem::DoesSupportWorldType(
    const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game
        || WorldType == EWorldType::PIE;
}

void UAAArenaFighterRuntimeSubsystem::OnWorldBeginPlay(
    UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    EntityFactory =
        NewObject<UAAArenaFighterEntityFactory>(&InWorld);
    if (UA3GameRuntimeSubsystem* Runtime =
        InWorld.GetSubsystem<UA3GameRuntimeSubsystem>())
    {
        Runtime->SetEntityFactory(EntityFactory);
        UE_LOG(
            LogTemp,
            Display,
            TEXT(
                "[A3Game] Arena Fighter example factory "
                "registered"));
    }
}

void UAAArenaFighterRuntimeSubsystem::Deinitialize()
{
    if (UWorld* World = GetWorld())
    {
        if (UA3GameRuntimeSubsystem* Runtime =
            World->GetSubsystem<UA3GameRuntimeSubsystem>())
        {
            Runtime->SetEntityFactory(nullptr);
        }
    }
    EntityFactory = nullptr;
    Super::Deinitialize();
}
