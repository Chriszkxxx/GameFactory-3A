#pragma once

#include "CoreMinimal.h"
#include "AAAGameRuntimeTypes.generated.h"

UENUM(BlueprintType)
enum class EAAAGameControlMode : uint8
{
    Exclusive,
    Priority,
    Assisted,
    Observing
};

UENUM(BlueprintType)
enum class EAAAGameLocomotionState : uint8
{
    Idle,
    Walk,
    Run,
    Jump
};

USTRUCT(BlueprintType)
struct AAAGAMEPLAYABLE_API FAAAGameRuntimeInputState
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString WorldId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ParticipantId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ControllerId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString EntityId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    float MoveX = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    float MoveY = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    bool bRun = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    bool bJump = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    float Yaw = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    float Pitch = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    int32 Sequence = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    double TimestampSeconds = 0.0;
};

USTRUCT(BlueprintType)
struct AAAGAMEPLAYABLE_API FAAAGameEntitySpawnRequest
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString WorldId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ParticipantId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString EntityId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FTransform Transform = FTransform::Identity;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    TMap<FString, FString> Parameters;
};

USTRUCT(BlueprintType)
struct AAAGAMEPLAYABLE_API FAAAGameParticipantInfo
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ParticipantId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString WorldId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString UserId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString EntityId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    bool bOnline = true;
};

USTRUCT(BlueprintType)
struct AAAGAMEPLAYABLE_API FAAAGameControllerState
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ControllerId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ParticipantId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString WorldId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString Kind = TEXT("human");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    bool bOnline = true;
};

USTRUCT(BlueprintType)
struct AAAGAMEPLAYABLE_API FAAAGameControlBinding
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ControllerId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString EntityId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString WorldId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    EAAAGameControlMode Mode = EAAAGameControlMode::Exclusive;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    int32 Priority = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    bool bActive = true;
};

USTRUCT(BlueprintType)
struct AAAGAMEPLAYABLE_API FAAAGameEntitySnapshot
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString EntityId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString ActorLabel;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FRotator Rotation = FRotator::ZeroRotator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    EAAAGameLocomotionState LocomotionState = EAAAGameLocomotionState::Idle;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    FString MotionState = TEXT("idle");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    bool bPersistent = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AAAGame|Runtime")
    double LastInputTimeSeconds = 0.0;
};
