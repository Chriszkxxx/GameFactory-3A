#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "A3GamePreviewPlayerController.generated.h"

class AA3GamePreviewCharacter;

UCLASS(Blueprintable)
class A3GAMEPREVIEW_API AA3GamePreviewPlayerController
    : public APlayerController
{
    GENERATED_BODY()

public:
    AA3GamePreviewPlayerController();

    virtual void PlayerTick(float DeltaTime) override;
    virtual void SetupInputComponent() override;
    virtual void SetViewTarget(
        AActor* NewViewTarget,
        FViewTargetTransitionParams TransitionParams =
            FViewTargetTransitionParams()) override;

private:
    void InputTurn(float Value);
    void InputLookUp(float Value);
    void InputZoom(float Value);
    void InputMouseDown();
    void InputMouseUp();
    void InputShiftPressed();
    void InputShiftReleased();
    void InputWPressed();
    void InputWReleased();
    void InputSPressed();
    void InputSReleased();
    void InputAPressed();
    void InputAReleased();
    void InputDPressed();
    void InputDReleased();
    AA3GamePreviewCharacter* GetPreviewTarget() const;
    void ApplyPreviewInput(
        float YawDelta,
        float PitchDelta,
        float ZoomDelta,
        float PanYDelta = 0.0f,
        float PanZDelta = 0.0f);

    UPROPERTY(EditAnywhere, Category = "A3Game|Preview")
    float MouseYawScale = 0.45f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Preview")
    float MousePitchScale = 0.32f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Preview")
    float KeyboardYawSpeed = 145.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Preview")
    float KeyboardZoomSpeed = 900.0f;

    UPROPERTY(EditAnywhere, Category = "A3Game|Preview")
    float WheelZoomScale = 80.0f;

    UPROPERTY()
    TObjectPtr<AA3GamePreviewCharacter> PreviewTarget;

    bool bDragging = false;
    bool bShiftHeld = false;
    bool bWPressed = false;
    bool bSPressed = false;
    bool bAPressed = false;
    bool bDPressed = false;
};
