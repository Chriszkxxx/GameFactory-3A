#include "FPSExample.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/DamageType.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Subsystems/A3GameRuntimeSubsystem.h"

IMPLEMENT_MODULE(FFPSExampleModule, FPSExample)

AAAFPSCharacter::AAAFPSCharacter()
{
    PrimaryActorTick.bCanEverTick = false;
    bUseControllerRotationYaw = true;

    RuntimeEntityComponent =
        CreateDefaultSubobject<UA3GameRuntimeEntityComponent>(
            TEXT("RuntimeEntity"));

    GetCapsuleComponent()->InitCapsuleSize(42.0f, 88.0f);
    UCharacterMovementComponent* Movement =
        GetCharacterMovement();
    Movement->bOrientRotationToMovement = false;
    Movement->MaxWalkSpeed = WalkSpeed;

    FirstPersonCamera =
        CreateDefaultSubobject<UCameraComponent>(
            TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(GetCapsuleComponent());
    FirstPersonCamera->SetRelativeLocation(
        FVector(0.0f, 0.0f, 64.0f));
    FirstPersonCamera->bUsePawnControlRotation = true;
    FirstPersonCamera->FieldOfView = 90.0f;

    WeaponMesh = CreateDefaultSubobject<UStaticMeshComponent>(
        TEXT("WeaponMesh"));
    WeaponMesh->SetupAttachment(FirstPersonCamera);
    WeaponMesh->SetRelativeLocation(
        FVector(42.0f, 18.0f, -18.0f));
    WeaponMesh->SetCollisionEnabled(
        ECollisionEnabled::NoCollision);
    WeaponMesh->SetOnlyOwnerSee(true);

    GetMesh()->SetOwnerNoSee(true);
}

void AAAFPSCharacter::BeginPlay()
{
    Super::BeginPlay();
    InitialTransform = GetActorTransform();
    Health = MaxHealth;
    MagazineAmmo = MagazineSize;
}

float AAAFPSCharacter::TakeDamage(
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
    if (AppliedDamage <= 0.0f || Health <= 0.0f)
    {
        return AppliedDamage;
    }
    Health = FMath::Clamp(
        Health - AppliedDamage,
        0.0f,
        MaxHealth);
    if (Health <= 0.0f)
    {
        GetCharacterMovement()->DisableMovement();
    }
    if (UWorld* World = GetWorld())
    {
        if (UAAAFPSMechanicContractSubsystem* Contract =
            World->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>())
        {
            Contract->PublishEvent(
                Health <= 0.0f
                    ? (TeamId == 0
                        ? EAAAFPSMechanicEventType::
                            PlayerDefeated
                        : EAAAFPSMechanicEventType::
                            TargetDefeated)
                    : EAAAFPSMechanicEventType::HealthChanged);
        }
    }
    return AppliedDamage;
}

FString AAAFPSCharacter::GetRuntimeEntityId_Implementation() const
{
    return RuntimeEntityComponent
        ? RuntimeEntityComponent->EntityId
        : FString();
}

void AAAFPSCharacter::SetRuntimeEntityId_Implementation(
    const FString& EntityId)
{
    if (RuntimeEntityComponent)
    {
        RuntimeEntityComponent->SetRuntimeEntityId(EntityId);
    }
}

bool AAAFPSCharacter::ApplyRuntimeInput_Implementation(
    const FA3GameRuntimeInputState& InputState)
{
    if (!RuntimeEntityComponent
        || !RuntimeEntityComponent->ApplyRuntimeInput(InputState))
    {
        return false;
    }
    if (Controller)
    {
        Controller->SetControlRotation(
            FRotator(
                InputState.Pitch,
                InputState.Yaw,
                0.0f));
    }
    else
    {
        SetActorRotation(
            FRotator(0.0f, InputState.Yaw, 0.0f));
    }
    ApplyControlInput(
        InputState.MoveX,
        InputState.MoveY,
        InputState.bRun,
        InputState.bJump);
    return true;
}

FA3GameEntitySnapshot AAAFPSCharacter::
GetRuntimeSnapshot_Implementation() const
{
    return RuntimeEntityComponent
        ? RuntimeEntityComponent->GetRuntimeSnapshot()
        : FA3GameEntitySnapshot();
}

void AAAFPSCharacter::ApplyControlInput(
    float MoveX,
    float MoveY,
    bool bRun,
    bool bJump)
{
    if (Health <= 0.0f)
    {
        return;
    }
    GetCharacterMovement()->MaxWalkSpeed =
        bRun ? RunSpeed : WalkSpeed;
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

bool AAAFPSCharacter::FireWeapon()
{
    if (Health <= 0.0f || MagazineAmmo <= 0)
    {
        return false;
    }
    --MagazineAmmo;
    if (UWorld* World = GetWorld())
    {
        if (UAAAFPSMechanicContractSubsystem* Contract =
            World->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>())
        {
            Contract->PublishEvent(
                EAAAFPSMechanicEventType::AmmoChanged);
        }
    }

    const FVector Start = FirstPersonCamera
        ? FirstPersonCamera->GetComponentLocation()
        : GetActorLocation();
    const FVector Direction = FirstPersonCamera
        ? FirstPersonCamera->GetForwardVector()
        : GetActorForwardVector();
    const FVector End = Start + Direction * WeaponRange;
    FCollisionQueryParams Params(
        SCENE_QUERY_STAT(A3GameFPSWeapon),
        true,
        this);
    Params.AddIgnoredActor(this);
    FHitResult Hit;
    if (GetWorld()->LineTraceSingleByChannel(
            Hit,
            Start,
            End,
            ECC_Visibility,
            Params)
        && Hit.GetActor())
    {
        UGameplayStatics::ApplyPointDamage(
            Hit.GetActor(),
            WeaponDamage,
            Direction,
            Hit,
            GetController(),
            this,
            UDamageType::StaticClass());
    }
    return true;
}

bool AAAFPSCharacter::ReloadWeapon()
{
    const int32 Needed = MagazineSize - MagazineAmmo;
    const int32 Loaded = FMath::Min(Needed, ReserveAmmo);
    if (Loaded <= 0)
    {
        return false;
    }
    MagazineAmmo += Loaded;
    ReserveAmmo -= Loaded;
    if (UWorld* World = GetWorld())
    {
        if (UAAAFPSMechanicContractSubsystem* Contract =
            World->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>())
        {
            Contract->PublishEvent(
                EAAAFPSMechanicEventType::AmmoChanged);
        }
    }
    return true;
}

void AAAFPSCharacter::ResetCombatant()
{
    Health = MaxHealth;
    MagazineAmmo = MagazineSize;
    SetActorTransform(
        InitialTransform,
        false,
        nullptr,
        ETeleportType::TeleportPhysics);
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    GetCharacterMovement()->StopMovementImmediately();
}

float AAAFPSCharacter::GetHealthPercent() const
{
    return MaxHealth > 0.0f
        ? FMath::Clamp(Health / MaxHealth, 0.0f, 1.0f)
        : 0.0f;
}

void AAAFPSPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    if (!InputComponent)
    {
        return;
    }

    InputComponent->BindAxisKey(
        EKeys::MouseX,
        this,
        &AAAFPSPlayerController::InputTurn);
    InputComponent->BindAxisKey(
        EKeys::MouseY,
        this,
        &AAAFPSPlayerController::InputLookUp);
    InputComponent->BindKey(
        EKeys::W,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::SetForwardPressed);
    InputComponent->BindKey(
        EKeys::W,
        IE_Released,
        this,
        &AAAFPSPlayerController::SetForwardReleased);
    InputComponent->BindKey(
        EKeys::S,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::SetBackwardPressed);
    InputComponent->BindKey(
        EKeys::S,
        IE_Released,
        this,
        &AAAFPSPlayerController::SetBackwardReleased);
    InputComponent->BindKey(
        EKeys::D,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::SetRightPressed);
    InputComponent->BindKey(
        EKeys::D,
        IE_Released,
        this,
        &AAAFPSPlayerController::SetRightReleased);
    InputComponent->BindKey(
        EKeys::A,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::SetLeftPressed);
    InputComponent->BindKey(
        EKeys::A,
        IE_Released,
        this,
        &AAAFPSPlayerController::SetLeftReleased);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::SetRunPressed);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Released,
        this,
        &AAAFPSPlayerController::SetRunReleased);
    InputComponent->BindKey(
        EKeys::SpaceBar,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::SetJumpPressed);
    InputComponent->BindKey(
        EKeys::SpaceBar,
        IE_Released,
        this,
        &AAAFPSPlayerController::SetJumpReleased);
    InputComponent->BindKey(
        EKeys::LeftMouseButton,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::Fire);
    InputComponent->BindKey(
        EKeys::R,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::Reload);
    InputComponent->BindKey(
        EKeys::F5,
        IE_Pressed,
        this,
        &AAAFPSPlayerController::RestartEncounter);
}

void AAAFPSPlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if (AAAFPSCharacter* FPSPawn =
        Cast<AAAFPSCharacter>(GetPawn()))
    {
        FPSPawn->ApplyControlInput(
            (bRightPressed ? 1.0f : 0.0f)
                - (bLeftPressed ? 1.0f : 0.0f),
            (bForwardPressed ? 1.0f : 0.0f)
                - (bBackwardPressed ? 1.0f : 0.0f),
            bRunPressed,
            bJumpPressed);
    }
}

void AAAFPSPlayerController::InputTurn(float Value)
{
    AddYawInput(Value);
}

void AAAFPSPlayerController::InputLookUp(float Value)
{
    AddPitchInput(-Value);
}

void AAAFPSPlayerController::SetForwardPressed()
{
    bForwardPressed = true;
}

void AAAFPSPlayerController::SetForwardReleased()
{
    bForwardPressed = false;
}

void AAAFPSPlayerController::SetBackwardPressed()
{
    bBackwardPressed = true;
}

void AAAFPSPlayerController::SetBackwardReleased()
{
    bBackwardPressed = false;
}

void AAAFPSPlayerController::SetRightPressed()
{
    bRightPressed = true;
}

void AAAFPSPlayerController::SetRightReleased()
{
    bRightPressed = false;
}

void AAAFPSPlayerController::SetLeftPressed()
{
    bLeftPressed = true;
}

void AAAFPSPlayerController::SetLeftReleased()
{
    bLeftPressed = false;
}

void AAAFPSPlayerController::SetRunPressed()
{
    bRunPressed = true;
}

void AAAFPSPlayerController::SetRunReleased()
{
    bRunPressed = false;
}

void AAAFPSPlayerController::SetJumpPressed()
{
    bJumpPressed = true;
}

void AAAFPSPlayerController::SetJumpReleased()
{
    bJumpPressed = false;
}

void AAAFPSPlayerController::Fire()
{
    if (UWorld* World = GetWorld())
    {
        if (UAAAFPSMechanicContractSubsystem* Contract =
            World->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>())
        {
            Contract->ExecuteMechanicCommand(
                EAAAFPSMechanicCommand::Fire);
        }
    }
}

void AAAFPSPlayerController::Reload()
{
    if (UWorld* World = GetWorld())
    {
        if (UAAAFPSMechanicContractSubsystem* Contract =
            World->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>())
        {
            Contract->ExecuteMechanicCommand(
                EAAAFPSMechanicCommand::Reload);
        }
    }
}

void AAAFPSPlayerController::RestartEncounter()
{
    if (UWorld* World = GetWorld())
    {
        if (UAAAFPSMechanicContractSubsystem* Contract =
            World->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>())
        {
            Contract->ExecuteMechanicCommand(
                EAAAFPSMechanicCommand::RestartEncounter);
        }
    }
}

AAAFPSGameMode::AAAFPSGameMode()
{
    DefaultPawnClass = AAAFPSCharacter::StaticClass();
    PlayerControllerClass = AAAFPSPlayerController::StaticClass();
}

void AAAFPSGameMode::StartPlay()
{
    Super::StartPlay();
    AAAFPSCharacter* Player = Cast<AAAFPSCharacter>(
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
    AAAFPSCharacter* Target =
        GetWorld()->SpawnActor<AAAFPSCharacter>(
            AAAFPSCharacter::StaticClass(),
            Player->GetActorLocation()
                + Player->GetActorForwardVector() * 1200.0f,
            (Player->GetActorForwardVector() * -1.0f).Rotation(),
            Params);
    if (Target)
    {
        Target->SetTeamId(1);
        Target->Tags.AddUnique(FName(TEXT("A3GameFPSTarget")));
    }
    if (UAAAFPSMechanicContractSubsystem* Contract =
        GetWorld()->GetSubsystem<
            UAAAFPSMechanicContractSubsystem>())
    {
        Contract->SetPlayer(Player);
        Contract->SetEncounterActive(true);
        Contract->PublishEvent(
            EAAAFPSMechanicEventType::EncounterStarted);
    }
}

void AAAFPSGameMode::RestartEncounter()
{
    for (TActorIterator<AAAFPSCharacter> It(GetWorld());
        It;
        ++It)
    {
        It->ResetCombatant();
    }
    if (UAAAFPSMechanicContractSubsystem* Contract =
        GetWorld()->GetSubsystem<
            UAAAFPSMechanicContractSubsystem>())
    {
        Contract->SetEncounterActive(true);
        Contract->PublishEvent(
            EAAAFPSMechanicEventType::EncounterRestarted);
    }
}

bool UAAAFPSMechanicContractSubsystem::DoesSupportWorldType(
    const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game
        || WorldType == EWorldType::PIE;
}

FAAFPSMechanicState
UAAAFPSMechanicContractSubsystem::GetMechanicState() const
{
    FAAFPSMechanicState State;
    const AAAFPSCharacter* PlayerCharacter = Player.Get();
    if (PlayerCharacter)
    {
        State.PlayerHealth = PlayerCharacter->GetHealth();
        State.PlayerMaxHealth = PlayerCharacter->GetMaxHealth();
        State.MagazineAmmo =
            PlayerCharacter->GetMagazineAmmo();
        State.ReserveAmmo = PlayerCharacter->GetReserveAmmo();
    }

    if (const UWorld* World = GetWorld())
    {
        for (TActorIterator<AAAFPSCharacter> It(
                const_cast<UWorld*>(World));
            It;
            ++It)
        {
            const AAAFPSCharacter* Candidate = *It;
            if (Candidate
                && Candidate != PlayerCharacter
                && !Candidate->IsDefeated()
                && (!PlayerCharacter
                    || Candidate->GetTeamId()
                        != PlayerCharacter->GetTeamId()))
            {
                ++State.TargetsRemaining;
            }
        }
    }

    if (!bEncounterActive)
    {
        State.Phase = EAAAFPSGamePhase::NotStarted;
        State.ObjectiveText = TEXT("Prepare for encounter");
    }
    else if (!PlayerCharacter
        || PlayerCharacter->IsDefeated())
    {
        State.Phase = EAAAFPSGamePhase::Defeat;
        State.ObjectiveText = TEXT("Encounter failed");
    }
    else if (State.TargetsRemaining == 0)
    {
        State.Phase = EAAAFPSGamePhase::Victory;
        State.ObjectiveText = TEXT("Encounter complete");
    }
    else
    {
        State.Phase = EAAAFPSGamePhase::Active;
        State.ObjectiveText = TEXT("Eliminate all targets");
    }
    return State;
}

bool UAAAFPSMechanicContractSubsystem::
ExecuteMechanicCommand(EAAAFPSMechanicCommand Command)
{
    AAAFPSCharacter* PlayerCharacter = Player.Get();
    switch (Command)
    {
    case EAAAFPSMechanicCommand::Fire:
        return PlayerCharacter
            && PlayerCharacter->FireWeapon();
    case EAAAFPSMechanicCommand::Reload:
        return PlayerCharacter
            && PlayerCharacter->ReloadWeapon();
    case EAAAFPSMechanicCommand::RestartEncounter:
        if (AAAFPSGameMode* GameMode =
            GetWorld()
                ? GetWorld()->GetAuthGameMode<AAAFPSGameMode>()
                : nullptr)
        {
            GameMode->RestartEncounter();
            return true;
        }
        return false;
    default:
        return false;
    }
}

void UAAAFPSMechanicContractSubsystem::SetPlayer(
    AAAFPSCharacter* InPlayer)
{
    Player = InPlayer;
}

void UAAAFPSMechanicContractSubsystem::SetEncounterActive(
    bool bInEncounterActive)
{
    bEncounterActive = bInEncounterActive;
}

void UAAAFPSMechanicContractSubsystem::PublishEvent(
    EAAAFPSMechanicEventType Type)
{
    FAAFPSMechanicEvent Event;
    Event.Type = Type;
    Event.State = GetMechanicState();
    Event.WorldTimeSeconds = GetWorld()
        ? GetWorld()->GetTimeSeconds()
        : 0.0f;
    MechanicEvent.Broadcast(Event);
}

AActor* UAAAFPSEntityFactory::SpawnRuntimeEntity_Implementation(
    const FA3GameEntitySpawnRequest& Request)
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }
    AAAFPSCharacter* Character =
        World->SpawnActor<AAAFPSCharacter>(
            AAAFPSCharacter::StaticClass(),
            Request.Transform);
    if (!Character)
    {
        return nullptr;
    }
    IA3GameControllableEntity::Execute_SetRuntimeEntityId(
        Character,
        Request.EntityId);
    if (const FString* TeamValue =
        Request.Parameters.Find(TEXT("team_id")))
    {
        Character->SetTeamId(FCString::Atoi(**TeamValue));
    }
    return Character;
}

bool UAAAFPSRuntimeSubsystem::DoesSupportWorldType(
    const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game
        || WorldType == EWorldType::PIE;
}

void UAAAFPSRuntimeSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);
    EntityFactory = NewObject<UAAAFPSEntityFactory>(&InWorld);
    if (UA3GameRuntimeSubsystem* Runtime =
        InWorld.GetSubsystem<UA3GameRuntimeSubsystem>())
    {
        Runtime->SetEntityFactory(EntityFactory);
        UE_LOG(
            LogTemp,
            Display,
            TEXT("[A3Game] FPS example factory registered"));
    }
}

void UAAAFPSRuntimeSubsystem::Deinitialize()
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
