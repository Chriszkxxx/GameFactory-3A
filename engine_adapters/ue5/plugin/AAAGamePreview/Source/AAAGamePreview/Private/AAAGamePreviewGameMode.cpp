#include "AAAGamePreviewGameMode.h"

#include "AAAGamePreviewCharacter.h"
#include "AAAGamePreviewPlayerController.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"

AAAAGamePreviewGameMode::AAAAGamePreviewGameMode()
{
    PlayerControllerClass =
        AAAAGamePreviewPlayerController::StaticClass();
    DefaultPawnClass = nullptr;
    HUDClass = nullptr;
}

void AAAAGamePreviewGameMode::HandleStartingNewPlayer_Implementation(
    APlayerController* NewPlayer)
{
    AAAAGamePreviewCharacter* PreviewCharacter =
        EnsurePreviewStage();
    if (NewPlayer && PreviewCharacter)
    {
        NewPlayer->SetViewTarget(PreviewCharacter);
        NewPlayer->bShowMouseCursor = true;
        NewPlayer->SetInputMode(FInputModeGameAndUI());
    }
}

AAAAGamePreviewCharacter*
AAAAGamePreviewGameMode::EnsurePreviewStage()
{
    UWorld* World = GetWorld();
    if (!World)
    {
        return nullptr;
    }

    for (TActorIterator<AAAAGamePreviewCharacter> It(World); It; ++It)
    {
        if (IsValid(*It))
        {
            return *It;
        }
    }

    FActorSpawnParameters Params;
    Params.Name = TEXT("AAAGame_PreviewCharacter");
    Params.SpawnCollisionHandlingOverride =
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AAAAGamePreviewCharacter* PreviewCharacter =
        World->SpawnActor<AAAAGamePreviewCharacter>(
            AAAAGamePreviewCharacter::StaticClass(),
            FVector::ZeroVector,
            FRotator::ZeroRotator,
            Params);
    if (PreviewCharacter)
    {
        PreviewCharacter->Tags.AddUnique(
            FName(TEXT("AAAGame_PreviewCharacter")));
#if WITH_EDITOR
        PreviewCharacter->SetActorLabel(
            TEXT("AAAGame_PreviewCharacter"));
#endif
    }
    return PreviewCharacter;
}
