#include "AAAGamePreviewPlayerController.h"

#include "AAAGamePreviewCharacter.h"
#include "Components/InputComponent.h"
#include "InputCoreTypes.h"

AAAAGamePreviewPlayerController::AAAAGamePreviewPlayerController()
{
    bShowMouseCursor = true;
    bEnableClickEvents = true;
    bEnableMouseOverEvents = false;
}

void AAAAGamePreviewPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    if (!InputComponent)
    {
        return;
    }

    InputComponent->BindAxisKey(
        EKeys::MouseX,
        this,
        &AAAAGamePreviewPlayerController::InputTurn);
    InputComponent->BindAxisKey(
        EKeys::MouseY,
        this,
        &AAAAGamePreviewPlayerController::InputLookUp);
    InputComponent->BindAxisKey(
        EKeys::MouseWheelAxis,
        this,
        &AAAAGamePreviewPlayerController::InputZoom);
    InputComponent->BindKey(
        EKeys::LeftMouseButton,
        IE_Pressed,
        this,
        &AAAAGamePreviewPlayerController::InputMouseDown);
    InputComponent->BindKey(
        EKeys::LeftMouseButton,
        IE_Released,
        this,
        &AAAAGamePreviewPlayerController::InputMouseUp);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Pressed,
        this,
        &AAAAGamePreviewPlayerController::InputShiftPressed);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Released,
        this,
        &AAAAGamePreviewPlayerController::InputShiftReleased);
    InputComponent->BindKey(
        EKeys::W,
        IE_Pressed,
        this,
        &AAAAGamePreviewPlayerController::InputWPressed);
    InputComponent->BindKey(
        EKeys::W,
        IE_Released,
        this,
        &AAAAGamePreviewPlayerController::InputWReleased);
    InputComponent->BindKey(
        EKeys::S,
        IE_Pressed,
        this,
        &AAAAGamePreviewPlayerController::InputSPressed);
    InputComponent->BindKey(
        EKeys::S,
        IE_Released,
        this,
        &AAAAGamePreviewPlayerController::InputSReleased);
    InputComponent->BindKey(
        EKeys::A,
        IE_Pressed,
        this,
        &AAAAGamePreviewPlayerController::InputAPressed);
    InputComponent->BindKey(
        EKeys::A,
        IE_Released,
        this,
        &AAAAGamePreviewPlayerController::InputAReleased);
    InputComponent->BindKey(
        EKeys::D,
        IE_Pressed,
        this,
        &AAAAGamePreviewPlayerController::InputDPressed);
    InputComponent->BindKey(
        EKeys::D,
        IE_Released,
        this,
        &AAAAGamePreviewPlayerController::InputDReleased);
}

void AAAAGamePreviewPlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if (!IsLocalController())
    {
        return;
    }

    const float YawInput =
        (bDPressed ? 1.0f : 0.0f)
        + (bAPressed ? -1.0f : 0.0f);
    const float ZoomInput =
        (bSPressed ? 1.0f : 0.0f)
        + (bWPressed ? -1.0f : 0.0f);
    if (!FMath::IsNearlyZero(YawInput)
        || !FMath::IsNearlyZero(ZoomInput))
    {
        ApplyPreviewInput(
            YawInput * KeyboardYawSpeed * DeltaTime,
            0.0f,
            ZoomInput * KeyboardZoomSpeed * DeltaTime);
    }
}

void AAAAGamePreviewPlayerController::SetViewTarget(
    AActor* NewViewTarget,
    FViewTargetTransitionParams TransitionParams)
{
    Super::SetViewTarget(NewViewTarget, TransitionParams);
    if (AAAAGamePreviewCharacter* Preview =
            Cast<AAAAGamePreviewCharacter>(NewViewTarget))
    {
        PreviewTarget = Preview;
    }
}

void AAAAGamePreviewPlayerController::InputTurn(float Value)
{
    if (FMath::IsNearlyZero(Value) || !bDragging)
    {
        return;
    }
    if (bShiftHeld)
    {
        ApplyPreviewInput(
            0.0f,
            0.0f,
            0.0f,
            Value * MouseYawScale,
            0.0f);
    }
    else
    {
        ApplyPreviewInput(Value * MouseYawScale, 0.0f, 0.0f);
    }
}

void AAAAGamePreviewPlayerController::InputLookUp(float Value)
{
    if (FMath::IsNearlyZero(Value) || !bDragging)
    {
        return;
    }
    if (bShiftHeld)
    {
        ApplyPreviewInput(
            0.0f,
            0.0f,
            0.0f,
            0.0f,
            Value * MousePitchScale);
    }
    else
    {
        ApplyPreviewInput(
            0.0f,
            -Value * MousePitchScale,
            0.0f);
    }
}

void AAAAGamePreviewPlayerController::InputZoom(float Value)
{
    if (!FMath::IsNearlyZero(Value))
    {
        ApplyPreviewInput(
            0.0f,
            0.0f,
            -Value * WheelZoomScale);
    }
}

void AAAAGamePreviewPlayerController::InputMouseDown()
{
    bDragging = true;
    bShowMouseCursor = false;
    SetInputMode(FInputModeGameOnly());
}

void AAAAGamePreviewPlayerController::InputMouseUp()
{
    bDragging = false;
    bShowMouseCursor = true;
    SetInputMode(FInputModeGameAndUI());
}

void AAAAGamePreviewPlayerController::InputShiftPressed()
{
    bShiftHeld = true;
}

void AAAAGamePreviewPlayerController::InputShiftReleased()
{
    bShiftHeld = false;
}

void AAAAGamePreviewPlayerController::InputWPressed()
{
    bWPressed = true;
}

void AAAAGamePreviewPlayerController::InputWReleased()
{
    bWPressed = false;
}

void AAAAGamePreviewPlayerController::InputSPressed()
{
    bSPressed = true;
}

void AAAAGamePreviewPlayerController::InputSReleased()
{
    bSPressed = false;
}

void AAAAGamePreviewPlayerController::InputAPressed()
{
    bAPressed = true;
}

void AAAAGamePreviewPlayerController::InputAReleased()
{
    bAPressed = false;
}

void AAAAGamePreviewPlayerController::InputDPressed()
{
    bDPressed = true;
}

void AAAAGamePreviewPlayerController::InputDReleased()
{
    bDPressed = false;
}

AAAAGamePreviewCharacter*
AAAAGamePreviewPlayerController::GetPreviewTarget() const
{
    if (PreviewTarget && IsValid(PreviewTarget))
    {
        return PreviewTarget;
    }
    return Cast<AAAAGamePreviewCharacter>(GetViewTarget());
}

void AAAAGamePreviewPlayerController::ApplyPreviewInput(
    float YawDelta,
    float PitchDelta,
    float ZoomDelta,
    float PanYDelta,
    float PanZDelta)
{
    if (AAAAGamePreviewCharacter* Preview = GetPreviewTarget())
    {
        Preview->ApplyPreviewCameraInput(
            YawDelta,
            PitchDelta,
            ZoomDelta,
            PanYDelta,
            PanZDelta);
    }
}
