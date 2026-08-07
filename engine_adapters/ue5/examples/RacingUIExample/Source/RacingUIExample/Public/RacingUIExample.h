#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Modules/ModuleManager.h"
#include "RacingExample.h"
#include "RacingUIExample.generated.h"

UCLASS()
class RACINGUIEXAMPLE_API AAARacingUIHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};

UCLASS()
class RACINGUIEXAMPLE_API AAARacingUIGameMode
    : public AAARacingGameMode
{
    GENERATED_BODY()

public:
    AAARacingUIGameMode();
};

class FRacingUIExampleModule final : public IModuleInterface
{
};
