#include "A3GamePreviewPlayerController.h"

#include "A3GamePreviewCharacter.h"
#include "Components/InputComponent.h"
#include "InputCoreTypes.h"

AA3GamePreviewPlayerController::AA3GamePreviewPlayerController()
{
    bShowMouseCursor = true;
    bEnableClickEvents = true;
    bEnableMouseOverEvents = false;
}

void AA3GamePreviewPlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    if (!InputComponent)
    {
        return;
    }

    InputComponent->BindAxisKey(
        EKeys::MouseX,
        this,
        &AA3GamePreviewPlayerController::InputTurn);
    InputComponent->BindAxisKey(
        EKeys::MouseY,
        this,
        &AA3GamePreviewPlayerController::InputLookUp);
    InputComponent->BindAxisKey(
        EKeys::MouseWheelAxis,
        this,
        &AA3GamePreviewPlayerController::InputZoom);
    InputComponent->BindKey(
        EKeys::LeftMouseButton,
        IE_Pressed,
        this,
        &AA3GamePreviewPlayerController::InputMouseDown);
    InputComponent->BindKey(
        EKeys::LeftMouseButton,
        IE_Released,
        this,
        &AA3GamePreviewPlayerController::InputMouseUp);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Pressed,
        this,
        &AA3GamePreviewPlayerController::InputShiftPressed);
    InputComponent->BindKey(
        EKeys::LeftShift,
        IE_Released,
        this,
        &AA3GamePreviewPlayerController::InputShiftReleased);
    InputComponent->BindKey(
        EKeys::W,
        IE_Pressed,
        this,
        &AA3GamePreviewPlayerController::InputWPressed);
    InputComponent->BindKey(
        EKeys::W,
        IE_Released,
        this,
        &AA3GamePreviewPlayerController::InputWReleased);
    InputComponent->BindKey(
        EKeys::S,
        IE_Pressed,
        this,
        &AA3GamePreviewPlayerController::InputSPressed);
    InputComponent->BindKey(
        EKeys::S,
        IE_Released,
        this,
        &AA3GamePreviewPlayerController::InputSReleased);
    InputComponent->BindKey(
        EKeys::A,
        IE_Pressed,
        this,
        &AA3GamePreviewPlayerController::InputAPressed);
    InputComponent->BindKey(
        EKeys::A,
        IE_Released,
        this,
        &AA3GamePreviewPlayerController::InputAReleased);
    InputComponent->BindKey(
        EKeys::D,
        IE_Pressed,
        this,
        &AA3GamePreviewPlayerController::InputDPressed);
    InputComponent->BindKey(
        EKeys::D,
        IE_Released,
        this,
        &AA3GamePreviewPlayerController::InputDReleased);
}

void AA3GamePreviewPlayerController::PlayerTick(float DeltaTime)
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

void AA3GamePreviewPlayerController::SetViewTarget(
    AActor* NewViewTarget,
    FViewTargetTransitionParams TransitionParams)
{
    Super::SetViewTarget(NewViewTarget, TransitionParams);
    if (AA3GamePreviewCharacter* Preview =
            Cast<AA3GamePreviewCharacter>(NewViewTarget))
    {
        PreviewTarget = Preview;
    }
}

void AA3GamePreviewPlayerController::InputTurn(float Value)
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

void AA3GamePreviewPlayerController::InputLookUp(float Value)
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

void AA3GamePreviewPlayerController::InputZoom(float Value)
{
    if (!FMath::IsNearlyZero(Value))
    {
        ApplyPreviewInput(
            0.0f,
            0.0f,
            -Value * WheelZoomScale);
    }
}

void AA3GamePreviewPlayerController::InputMouseDown()
{
    bDragging = true;
    bShowMouseCursor = false;
    SetInputMode(FInputModeGameOnly());
}

void AA3GamePreviewPlayerController::InputMouseUp()
{
    bDragging = false;
    bShowMouseCursor = true;
    SetInputMode(FInputModeGameAndUI());
}

void AA3GamePreviewPlayerController::InputShiftPressed()
{
    bShiftHeld = true;
}

void AA3GamePreviewPlayerController::InputShiftReleased()
{
    bShiftHeld = false;
}

void AA3GamePreviewPlayerController::InputWPressed()
{
    bWPressed = true;
}

void AA3GamePreviewPlayerController::InputWReleased()
{
    bWPressed = false;
}

void AA3GamePreviewPlayerController::InputSPressed()
{
    bSPressed = true;
}

void AA3GamePreviewPlayerController::InputSReleased()
{
    bSPressed = false;
}

void AA3GamePreviewPlayerController::InputAPressed()
{
    bAPressed = true;
}

void AA3GamePreviewPlayerController::InputAReleased()
{
    bAPressed = false;
}

void AA3GamePreviewPlayerController::InputDPressed()
{
    bDPressed = true;
}

void AA3GamePreviewPlayerController::InputDReleased()
{
    bDPressed = false;
}

AA3GamePreviewCharacter*
AA3GamePreviewPlayerController::GetPreviewTarget() const
{
    if (PreviewTarget && IsValid(PreviewTarget))
    {
        return PreviewTarget;
    }
    return Cast<AA3GamePreviewCharacter>(GetViewTarget());
}

void AA3GamePreviewPlayerController::ApplyPreviewInput(
    float YawDelta,
    float PitchDelta,
    float ZoomDelta,
    float PanYDelta,
    float PanZDelta)
{
    if (AA3GamePreviewCharacter* Preview = GetPreviewTarget())
    {
        Preview->ApplyPreviewCameraInput(
            YawDelta,
            PitchDelta,
            ZoomDelta,
            PanYDelta,
            PanZDelta);
    }
}
