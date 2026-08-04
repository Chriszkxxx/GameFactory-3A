#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AAAGamePreviewCharacter.generated.h"

class UAnimSequence;
class UCameraComponent;
class UDirectionalLightComponent;
class UPointLightComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class USpringArmComponent;

UCLASS(Blueprintable)
class AAAGAMEPREVIEW_API AAAAGamePreviewCharacter : public AActor
{
    GENERATED_BODY()

public:
    AAAAGamePreviewCharacter();

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Preview")
    void SetPreviewCharacter(
        USkeletalMesh* InMesh,
        UAnimSequence* InIdleAnimation,
        float InScale = 1.0f,
        float InYaw = 0.0f);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Preview")
    void PlayPreviewAnimation(
        UAnimSequence* InAnimation,
        bool bLoop = true,
        float InPlayRate = 1.0f);

    UFUNCTION(BlueprintCallable, Category = "AAAGame|Preview")
    void ApplyPreviewCameraInput(
        float YawDelta,
        float PitchDelta,
        float ZoomDelta,
        float PanYDelta = 0.0f,
        float PanZDelta = 0.0f);

    UFUNCTION(BlueprintPure, Category = "AAAGame|Preview")
    UCameraComponent* GetPreviewCamera() const
    {
        return PreviewCamera;
    }

private:
    void ReframePreviewMesh();

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<USkeletalMeshComponent> PreviewMesh;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<USpringArmComponent> CameraBoom;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<UCameraComponent> PreviewCamera;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<UStaticMeshComponent> PreviewFloor;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<UDirectionalLightComponent> KeyLight;

    UPROPERTY(VisibleAnywhere, Category = "AAAGame|Preview")
    TObjectPtr<UPointLightComponent> FillLight;

    float CameraYaw = 0.0f;
    float CameraPitch = -6.0f;
};
