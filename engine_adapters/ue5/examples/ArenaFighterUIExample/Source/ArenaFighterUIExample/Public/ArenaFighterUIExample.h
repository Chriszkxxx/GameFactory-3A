#pragma once

#include "ArenaFighterExample.h"
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Modules/ModuleManager.h"
#include "ArenaFighterUIExample.generated.h"

UCLASS()
class ARENAFIGHTERUIEXAMPLE_API AAAArenaFighterUIHUD
    : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;

private:
    void DrawHealthBar(
        const FString& Label,
        float HealthPercent,
        float X,
        float Y,
        float Width,
        const FLinearColor& Color);
};

UCLASS()
class ARENAFIGHTERUIEXAMPLE_API AAAArenaFighterUIGameMode
    : public AAAArenaFighterGameMode
{
    GENERATED_BODY()

public:
    AAAArenaFighterUIGameMode();
};

class FArenaFighterUIExampleModule final
    : public IModuleInterface
{
};
