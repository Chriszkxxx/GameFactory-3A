#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "AAAGamePreviewGameMode.generated.h"

class AAAAGamePreviewCharacter;
class APlayerController;

UCLASS()
class AAAGAMEPREVIEW_API AAAAGamePreviewGameMode
    : public AGameModeBase
{
    GENERATED_BODY()

public:
    AAAAGamePreviewGameMode();

    virtual void HandleStartingNewPlayer_Implementation(
        APlayerController* NewPlayer) override;

private:
    AAAAGamePreviewCharacter* EnsurePreviewStage();
};
