#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "A3GamePreviewCharacter.generated.h"

class UAnimSequence;
class UCameraComponent;
class UDirectionalLightComponent;
class UPointLightComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class USpringArmComponent;

UCLASS(Blueprintable)
class A3GAMEPREVIEW_API AA3GamePreviewCharacter : public AActor
{
    GENERATED_BODY()

public:
    AA3GamePreviewCharacter();

    UFUNCTION(BlueprintCallable, Category = "A3Game|Preview")
    void SetPreviewCharacter(
        USkeletalMesh* InMesh,
        UAnimSequence* InIdleAnimation,
        float InScale = 1.0f,
        float InYaw = 0.0f);

    UFUNCTION(BlueprintCallable, Category = "A3Game|Preview")
    void PlayPreviewAnimation(
        UAnimSequence* InAnimation,
        bool bLoop = true,
        float InPlayRate = 1.0f);

    UFUNCTION(BlueprintCallable, Category = "A3Game|Preview")
    void ApplyPreviewCameraInput(
        float YawDelta,
        float PitchDelta,
        float ZoomDelta,
        float PanYDelta = 0.0f,
        float PanZDelta = 0.0f);

    UFUNCTION(BlueprintPure, Category = "A3Game|Preview")
    UCameraComponent* GetPreviewCamera() const
    {
        return PreviewCamera;
    }

private:
    void ReframePreviewMesh();

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<USkeletalMeshComponent> PreviewMesh;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<UCameraComponent> PreviewCamera;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<UStaticMeshComponent> PreviewFloor;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<UDirectionalLightComponent> KeyLight;

    UPROPERTY(VisibleAnywhere, Category = "A3Game|Preview")
    TObjectPtr<UPointLightComponent> FillLight;

    float CameraYaw = 0.0f;
    float CameraPitch = -6.0f;
};
