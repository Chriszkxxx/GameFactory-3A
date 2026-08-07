#pragma once

#include "CoreMinimal.h"
#include "FPSExample.h"
#include "GameFramework/HUD.h"
#include "Modules/ModuleManager.h"
#include "FPSUIExample.generated.h"

UCLASS()
class FPSUIEXAMPLE_API AAAFPSUIHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};

UCLASS()
class FPSUIEXAMPLE_API AAAFPSUIGameMode : public AAAFPSGameMode
{
    GENERATED_BODY()

public:
    AAAFPSUIGameMode();
};

class FFPSUIExampleModule final : public IModuleInterface
{
};
