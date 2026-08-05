#include "RacingExample.h"

#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/InputComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Subsystems/A3GameRuntimeSubsystem.h"

IMPLEMENT_MODULE(FRacingExampleModule, RacingExample)

AAARacingPawn::AAARacingPawn()
{
    PrimaryActorTick.bCanEverTick = true;

    CollisionBox = CreateDefaultSubobject<UBoxComponent>(
        TEXT("VehicleCollision"));
    SetRootComponent(CollisionBox);
    CollisionBox->InitBoxExtent(FVector(112.0f, 58.0f, 34.0f));
    CollisionBox->SetCollisionProfileName(TEXT("Pawn"));
    CollisionBox->SetCollisionEnabled(
        ECollisionEnabled::QueryAndPhysics);

    RuntimeEntityComponent =
        CreateDefaultSubobject<UA3GameRuntimeEntityComponent>(
            TEXT("RuntimeEntity"));

    VehicleMesh = CreateDefaultSubobject<UStaticMeshComponent>(
        TEXT("VehicleMesh"));
    VehicleMesh->SetupAttachment(RootComponent);
    VehicleMesh->SetCollisionEnabled(
        ECollisionEnabled::NoCollision);
    VehicleMesh->SetRelativeScale3D(
        FVector(2.2f, 1.1f, 0.55f));
    if (UStaticMesh* Cube = LoadObject<UStaticMesh>(
            nullptr,
            TEXT("/Engine/BasicShapes/Cube.Cube")))
    {
        VehicleMesh->SetStaticMesh(Cube);
    }

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(
        TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 620.0f;
    CameraBoom->SetRelativeLocation(
        FVector(0.0f, 0.0f, 115.0f));
    CameraBoom->SetRelativeRotation(
        FRotator(-12.0f, 0.0f, 0.0f));
    CameraBoom->bDoCollisionTest = true;
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 7.0f;

    FollowCamera = CreateDefaultSubobject<UCameraComponent>(
        TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(
        CameraBoom,
        USpringArmComponent::SocketName);
    FollowCamera->FieldOfView = 82.0f;
}

void AAARacingPawn::BeginPlay()
{
    Super::BeginPlay();
    InitialTransform = GetActorTransform();
    NitroAmount = NitroCapacity;
}

void AAARacingPawn::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (DeltaSeconds <= 0.0f)
    {
        return;
    }

    UWorld* World = GetWorld();
    if (World
        && World->GetTimeSeconds() - LastInputTimeSeconds > 0.35f)
    {
        PendingSteering = 0.0f;
        PendingThrottle = 0.0f;
        bPendingBoost = false;
        bPendingHandbrake = false;
    }

    bHandbrakeActive = bPendingHandbrake;
    bBoostActive = bPendingBoost
        && PendingThrottle > 0.0f
        && NitroAmount > 0.0f
        && !bHandbrakeActive;
    if (bBoostActive)
    {
        NitroAmount = FMath::Max(
            0.0f,
            NitroAmount - NitroBurnRate * DeltaSeconds);
    }
    else
    {
        NitroAmount = FMath::Min(
            NitroCapacity,
            NitroAmount + NitroRechargeRate * DeltaSeconds);
    }

    const float ForwardLimit =
        MaxSpeed * (bBoostActive ? BoostMultiplier : 1.0f);
    const float TargetSpeed = PendingThrottle >= 0.0f
        ? ForwardLimit * PendingThrottle
        : ReverseSpeed * PendingThrottle;
    const float SpeedChange = bHandbrakeActive
        ? Braking * 1.35f
        : (FMath::Abs(TargetSpeed) < FMath::Abs(CurrentSpeed)
            ? Braking
            : Acceleration);
    CurrentSpeed = FMath::FInterpConstantTo(
        CurrentSpeed,
        bHandbrakeActive ? 0.0f : TargetSpeed,
        DeltaSeconds,
        SpeedChange);

    const float SpeedRatio = FMath::Clamp(
        FMath::Abs(CurrentSpeed) / FMath::Max(MaxSpeed, 1.0f),
        0.0f,
        BoostMultiplier);
    if (FMath::Abs(CurrentSpeed) > 5.0f)
    {
        const float DirectionSign =
            CurrentSpeed >= 0.0f ? 1.0f : -1.0f;
        AddActorLocalRotation(
            FRotator(
                0.0f,
                PendingSteering
                    * TurnRate
                    * SpeedRatio
                    * DirectionSign
                    * DeltaSeconds,
                0.0f));
    }

    FHitResult Hit;
    AddActorWorldOffset(
        GetActorForwardVector() * CurrentSpeed * DeltaSeconds,
        true,
        &Hit);
    if (Hit.bBlockingHit)
    {
        CurrentSpeed = 0.0f;
    }
}

FString AAARacingPawn::GetRuntimeEntityId_Implementation() const
{
    return RuntimeEntityComponent
        ? RuntimeEntityComponent->EntityId
        : FString();
}

void AAARacingPawn::SetRuntimeEntityId_Implementation(
    const FString& EntityId)
{
    if (RuntimeEntityComponent)
    {
        RuntimeEntityComponent->SetRuntimeEntityId(EntityId);
    }
}

bool AAARacingPawn::ApplyRuntimeInput_Implementation(
    const FA3GameRuntimeInputState& InputState)
{
    if (!RuntimeEntityComponent
        || !RuntimeEntityComponent->ApplyRuntimeInput(InputState))
    {
        return false;
    }
    SetActorRotation(FRotator(0.0f, InputState.Yaw, 0.0f));
    ApplyDriveInput(
        InputState.MoveX,
        InputState.MoveY,
        InputState.bRun,
        InputState.bJump);
    return true;
}

FA3GameEntitySnapshot AAARacingPawn::
GetRuntimeSnapshot_Implementation() const
{
    FA3GameEntitySnapshot Snapshot = RuntimeEntityComponent
        ? RuntimeEntityComponent->GetRuntimeSnapshot()
        : FA3GameEntitySnapshot();
    Snapshot.MotionState = FString::Printf(
        TEXT("drive:%.1f"),
        GetSpeedKph());
    return Snapshot;
}

void AAARacingPawn::ApplyDriveInput(
    float Steering,
    float Throttle,
    bool bBoost,
    bool bHandbrake)
{
    PendingSteering = FMath::Clamp(Steering, -1.0f, 1.0f);
    PendingThrottle = FMath::Clamp(Throttle, -1.0f, 1.0f);
    bPendingBoost = bBoost;
    bPendingHandbrake = bHandbrake;
    LastInputTimeSeconds = GetWorld()
        ? GetWorld()->GetTimeSeconds()
        : 0.0f;
}

void AAARacingPawn::ResetVehicle()
{
    CurrentSpeed = 0.0f;
    PendingSteering = 0.0f;
    PendingThrottle = 0.0f;
    bPendingBoost = false;
    bPendingHandbrake = false;
    SetActorTransform(
        InitialTransform,
        false,
        nullptr,
        ETeleportType::TeleportPhysics);
}

float AAARacingPawn::GetSpeedKph() const
{
    return FMath::Abs(CurrentSpeed) * 0.036f;
}

float AAARacingPawn::GetNitroPercent() const
{
    return NitroCapacity > 0.0f
        ? FMath::Clamp(
            NitroAmount / NitroCapacity,
            0.0f,
            1.0f)
        : 0.0f;
}

void AAARacingPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    if (!InputComponent)
    {
        return;
    }

    InputComponent->BindKey(
        EKeys::W,
        IE_Pressed,
        this,
        &AAARacingPlayerController::SetForwardPressed);
    InputComponent->BindKey(
        EKeys::W,
        IE_Released,
        this,
        &AAARacingPlayerController::SetForwardReleased);
    InputComponent->BindKey(
        EKeys::S,
        IE_Pressed,
        this,
        &AAARacingPlayerController::SetBackwardPressed);
    InputComponent->BindKey(
        EKeys::S,
        IE_Released,
        this,
        &AAARacingPlayerController::SetBackwardReleased);
    InputComponent->BindKey(
        EKeys::D,
        IE_Pressed,
        this,
        &AAARacingPlayerController::SetRightPressed);
    InputComponent->BindKey(
        EKeys::D,
        IE_Released,
        this,
        &AAARacingPlayerController::SetRightReleased);
    InputComponent->BindKey(
        EKeys::A,
        IE_Pressed,
        this,
        &AAARacingPlayerController::SetLeftPressed);
    InputComponent->BindKey(
        EKeys::A,
        IE_Released,
        this,
        &AAARacingPlayerController::SetLeftReleased);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Pressed,
        this,
        &AAARacingPlayerController::SetBoostPressed);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Released,
        this,
        &AAARacingPlayerController::SetBoostReleased);
    InputComponent->BindKey(
        EKeys::SpaceBar,
        IE_Pressed,
        this,
        &AAARacingPlayerController::SetHandbrakePressed);
    InputComponent->BindKey(
        EKeys::SpaceBar,
        IE_Released,
        this,
        &AAARacingPlayerController::SetHandbrakeReleased);
    InputComponent->BindKey(
        EKeys::R,
        IE_Pressed,
        this,
        &AAARacingPlayerController::ResetVehicle);
}

void AAARacingPlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if (AAARacingPawn* Vehicle =
        Cast<AAARacingPawn>(GetPawn()))
    {
        Vehicle->ApplyDriveInput(
            (bRightPressed ? 1.0f : 0.0f)
                - (bLeftPressed ? 1.0f : 0.0f),
            (bForwardPressed ? 1.0f : 0.0f)
                - (bBackwardPressed ? 1.0f : 0.0f),
            bBoostPressed,
            bHandbrakePressed);
    }
}

void AAARacingPlayerController::SetForwardPressed()
{
    bForwardPressed = true;
}

void AAARacingPlayerController::SetForwardReleased()
{
    bForwardPressed = false;
}

void AAARacingPlayerController::SetBackwardPressed()
{
    bBackwardPressed = true;
}

void AAARacingPlayerController::SetBackwardReleased()
{
    bBackwardPressed = false;
}

void AAARacingPlayerController::SetRightPressed()
{
    bRightPressed = true;
}

void AAARacingPlayerController::SetRightReleased()
{
    bRightPressed = false;
}

void AAARacingPlayerController::SetLeftPressed()
{
    bLeftPressed = true;
}

void AAARacingPlayerController::SetLeftReleased()
{
    bLeftPressed = false;
}

void AAARacingPlayerController::SetBoostPressed()
{
    bBoostPressed = true;
}

void AAARacingPlayerController::SetBoostReleased()
{
    bBoostPressed = false;
}

void AAARacingPlayerController::SetHandbrakePressed()
{
    bHandbrakePressed = true;
}

void AAARacingPlayerController::SetHandbrakeReleased()
{
    bHandbrakePressed = false;
}

void AAARacingPlayerController::ResetVehicle()
{
    if (AAARacingPawn* Vehicle =
        Cast<AAARacingPawn>(GetPawn()))
    {
        Vehicle->ResetVehicle();
    }
}

void AAARacingHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas)
    {
        return;
    }
    AAARacingPawn* Vehicle =
        Cast<AAARacingPawn>(GetOwningPawn());
    if (!Vehicle)
    {
        return;
    }

    const FLinearColor Primary(
        0.94f,
        0.97f,
        1.0f,
        1.0f);
    const FLinearColor Accent(
        0.02f,
        0.72f,
        0.95f,
        1.0f);
    DrawText(
        FString::Printf(
            TEXT("%03d KM/H"),
            FMath::RoundToInt(Vehicle->GetSpeedKph())),
        Primary,
        Canvas->SizeX - 250.0f,
        Canvas->SizeY - 92.0f,
        GEngine ? GEngine->GetLargeFont() : nullptr);
    DrawText(
        Vehicle->IsHandbraking()
            ? TEXT("HANDBRAKE")
            : Vehicle->IsBoosting()
                ? TEXT("NITRO")
                : TEXT(""),
        Accent,
        42.0f,
        42.0f,
        GEngine ? GEngine->GetLargeFont() : nullptr);
    DrawRect(
        FLinearColor(0.02f, 0.02f, 0.02f, 0.9f),
        Canvas->SizeX - 250.0f,
        Canvas->SizeY - 122.0f,
        200.0f,
        12.0f);
    DrawRect(
        Accent,
        Canvas->SizeX - 248.0f,
        Canvas->SizeY - 120.0f,
        196.0f * Vehicle->GetNitroPercent(),
        8.0f);
}

AAARacingGameMode::AAARacingGameMode()
{
    DefaultPawnClass = AAARacingPawn::StaticClass();
    PlayerControllerClass =
        AAARacingPlayerController::StaticClass();
    HUDClass = AAARacingHUD::StaticClass();
}

AActor* UAAARacingEntityFactory::
SpawnRuntimeEntity_Implementation(
    const FA3GameEntitySpawnRequest& Request)
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }
    AAARacingPawn* Vehicle =
        World->SpawnActor<AAARacingPawn>(
            AAARacingPawn::StaticClass(),
            Request.Transform);
    if (!Vehicle)
    {
        return nullptr;
    }
    IA3GameControllableEntity::Execute_SetRuntimeEntityId(
        Vehicle,
        Request.EntityId);
    return Vehicle;
}

bool UAAARacingRuntimeSubsystem::DoesSupportWorldType(
    const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game
        || WorldType == EWorldType::PIE;
}

void UAAARacingRuntimeSubsystem::OnWorldBeginPlay(
    UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    EntityFactory =
        NewObject<UAAARacingEntityFactory>(&InWorld);
    if (UA3GameRuntimeSubsystem* Runtime =
        InWorld.GetSubsystem<UA3GameRuntimeSubsystem>())
    {
        Runtime->SetEntityFactory(EntityFactory);
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[A3Game] Racing example factory registered"));
    }
}

void UAAARacingRuntimeSubsystem::Deinitialize()
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
