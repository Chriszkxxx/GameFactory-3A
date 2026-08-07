#include "A3GamePreviewGameMode.h"

#include "A3GamePreviewCharacter.h"
#include "A3GamePreviewPlayerController.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"

AA3GamePreviewGameMode::AA3GamePreviewGameMode()
{
    PlayerControllerClass =
        AA3GamePreviewPlayerController::StaticClass();
    DefaultPawnClass = nullptr;
    HUDClass = nullptr;
}

void AA3GamePreviewGameMode::HandleStartingNewPlayer_Implementation(
    APlayerController* NewPlayer)
{
    AA3GamePreviewCharacter* PreviewCharacter =
        EnsurePreviewStage();
    if (NewPlayer && PreviewCharacter)
    {
        NewPlayer->SetViewTarget(PreviewCharacter);
        NewPlayer->bShowMouseCursor = true;
        NewPlayer->SetInputMode(FInputModeGameAndUI());
    }
}

AA3GamePreviewCharacter*
AA3GamePreviewGameMode::EnsurePreviewStage()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }

    for (TActorIterator<AA3GamePreviewCharacter> It(World); It; ++It)
    {
        if (IsValid(*It))
        {
            return *It;
        }
    }

    FActorSpawnParameters Params;
    Params.Name = TEXT("A3Game_PreviewCharacter");
    Params.SpawnCollisionHandlingOverride =
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AA3GamePreviewCharacter* PreviewCharacter =
        World->SpawnActor<AA3GamePreviewCharacter>(
            AA3GamePreviewCharacter::StaticClass(),
            FVector::ZeroVector,
            FRotator::ZeroRotator,
            Params);
    if (PreviewCharacter)
    {
        PreviewCharacter->Tags.AddUnique(
            FName(TEXT("A3Game_PreviewCharacter")));
#if WITH_EDITOR
        PreviewCharacter->SetActorLabel(
            TEXT("A3Game_PreviewCharacter"));
#endif
    }
    return PreviewCharacter;
}
