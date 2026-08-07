#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "A3GamePreviewGameMode.generated.h"

class AA3GamePreviewCharacter;
class APlayerController;

UCLASS()
class A3GAMEPREVIEW_API AA3GamePreviewGameMode
    : public AGameModeBase
{
    GENERATED_BODY()

public:
    AA3GamePreviewGameMode();

    virtual void HandleStartingNewPlayer_Implementation(
        APlayerController* NewPlayer) override;

private:
    AA3GamePreviewCharacter* EnsurePreviewStage();
};
