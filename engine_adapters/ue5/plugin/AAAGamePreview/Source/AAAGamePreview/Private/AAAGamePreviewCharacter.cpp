#include "AAAGamePreviewCharacter.h"

#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/SpringArmComponent.h"

AAAAGamePreviewCharacter::AAAAGamePreviewCharacter()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = false;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(
        TEXT("SceneRoot"));
    RootComponent = SceneRoot;

    PreviewFloor = CreateDefaultSubobject<UStaticMeshComponent>(
        TEXT("PreviewFloor"));
    PreviewFloor->SetupAttachment(SceneRoot);
    PreviewFloor->SetRelativeScale3D(FVector(6.0f, 6.0f, 0.1f));
    PreviewFloor->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    PreviewFloor->SetHiddenInGame(true);
    if (UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(
            nullptr,
            TEXT("/Engine/BasicShapes/Plane.Plane")))
    {
        PreviewFloor->SetStaticMesh(PlaneMesh);
    }

    PreviewMesh = CreateDefaultSubobject<USkeletalMeshComponent>(
        TEXT("PreviewMesh"));
    PreviewMesh->SetupAttachment(SceneRoot);
    PreviewMesh->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
    PreviewMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(
        TEXT("PreviewCameraBoom"));
    CameraBoom->SetupAttachment(SceneRoot);
    CameraBoom->SetRelativeLocation(FVector(0.0f, 0.0f, 80.0f));
    CameraBoom->TargetArmLength = 850.0f;
    CameraBoom->SetRelativeRotation(
        FRotator(CameraPitch, CameraYaw, 0.0f));
    CameraBoom->bUsePawnControlRotation = false;

    PreviewCamera = CreateDefaultSubobject<UCameraComponent>(
        TEXT("PreviewCamera"));
    PreviewCamera->SetupAttachment(
        CameraBoom,
        USpringArmComponent::SocketName);
    PreviewCamera->FieldOfView = 45.0f;

    KeyLight = CreateDefaultSubobject<UDirectionalLightComponent>(
        TEXT("PreviewKeyLight"));
    KeyLight->SetupAttachment(SceneRoot);
    KeyLight->SetRelativeRotation(FRotator(-45.0f, -35.0f, 0.0f));
    KeyLight->Intensity = 4.0f;

    FillLight = CreateDefaultSubobject<UPointLightComponent>(
        TEXT("PreviewFillLight"));
    FillLight->SetupAttachment(SceneRoot);
    FillLight->SetRelativeLocation(FVector(180.0f, -240.0f, 180.0f));
    FillLight->Intensity = 800.0f;
    FillLight->AttenuationRadius = 600.0f;
}

void AAAAGamePreviewCharacter::SetPreviewCharacter(
    USkeletalMesh* InMesh,
    UAnimSequence* InIdleAnimation,
    float InScale,
    float InYaw)
{
    const float SafeScale = FMath::Max(0.01f, InScale);
    SetActorScale3D(FVector(SafeScale));
    SetActorRotation(FRotator(0.0f, InYaw, 0.0f));
    PreviewMesh->SetRelativeLocation(FVector::ZeroVector);
    PreviewMesh->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));

    if (InMesh)
    {
        PreviewMesh->SetSkeletalMesh(InMesh);
        ReframePreviewMesh();
    }
    if (InIdleAnimation)
    {
        PlayPreviewAnimation(InIdleAnimation);
    }
}

void AAAAGamePreviewCharacter::ReframePreviewMesh()
{
    if (!PreviewMesh || !PreviewMesh->GetSkeletalMeshAsset())
    {
        return;
    }

    PreviewMesh->UpdateComponentToWorld();
    const FBoxSphereBounds Bounds =
        PreviewMesh->CalcBounds(PreviewMesh->GetComponentTransform());
    const float SafeScale = FMath::Max(0.01f, GetActorScale3D().Z);
    const float FloorWorldZ = PreviewFloor
        ? PreviewFloor->GetComponentLocation().Z
        : GetActorLocation().Z;
    const float MeshBottomZ = Bounds.Origin.Z - Bounds.BoxExtent.Z;
    const float MeshTopZ = Bounds.Origin.Z + Bounds.BoxExtent.Z;
    const float MeshHeight =
        FMath::Max(100.0f, MeshTopZ - MeshBottomZ);

    FVector MeshLocation = PreviewMesh->GetRelativeLocation();
    MeshLocation.Z +=
        (FloorWorldZ - MeshBottomZ + 2.0f) / SafeScale;
    PreviewMesh->SetRelativeLocation(MeshLocation);

    CameraBoom->TargetArmLength = FMath::Clamp(
        MeshHeight * 2.0f,
        650.0f,
        1400.0f);
    CameraBoom->SetRelativeLocation(FVector(
        0.0f,
        0.0f,
        FMath::Clamp(MeshHeight * 0.45f, 80.0f, 220.0f)
            / SafeScale));
    CameraYaw = 0.0f;
    CameraPitch = -6.0f;
    CameraBoom->SetRelativeRotation(
        FRotator(CameraPitch, CameraYaw, 0.0f));
}

void AAAAGamePreviewCharacter::PlayPreviewAnimation(
    UAnimSequence* InAnimation,
    bool bLoop,
    float InPlayRate)
{
    if (!InAnimation)
    {
        return;
    }
    PreviewMesh->PlayAnimation(InAnimation, bLoop);
    PreviewMesh->SetPlayRate(FMath::Max(0.01f, InPlayRate));
}

void AAAAGamePreviewCharacter::ApplyPreviewCameraInput(
    float YawDelta,
    float PitchDelta,
    float ZoomDelta,
    float PanYDelta,
    float PanZDelta)
{
    if (!CameraBoom)
    {
        return;
    }

    CameraYaw += YawDelta;
    CameraPitch = FMath::Clamp(
        CameraPitch + PitchDelta,
        -65.0f,
        25.0f);
    CameraBoom->SetRelativeRotation(
        FRotator(CameraPitch, CameraYaw, 0.0f));
    CameraBoom->TargetArmLength = FMath::Clamp(
        CameraBoom->TargetArmLength + ZoomDelta,
        250.0f,
        2200.0f);

    FVector BoomLocation = CameraBoom->GetRelativeLocation();
    BoomLocation.Y = FMath::Clamp(
        BoomLocation.Y + PanYDelta,
        -450.0f,
        450.0f);
    BoomLocation.Z = FMath::Clamp(
        BoomLocation.Z + PanZDelta,
        20.0f,
        520.0f);
    CameraBoom->SetRelativeLocation(BoomLocation);
}
