#include "RacingUIExample.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "RacingMechanicContract.h"

IMPLEMENT_MODULE(FRacingUIExampleModule, RacingUIExample)

void AAARacingUIHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas)
    {
        return;
    }

    UAAARacingMechanicContractSubsystem* Contract =
        GetWorld()
            ? GetWorld()->GetSubsystem<
                UAAARacingMechanicContractSubsystem>()
            : nullptr;
    if (!Contract)
    {
        return;
    }
    const FAAARacingMechanicState State =
        Contract->GetMechanicState();

    const FLinearColor Primary(
        0.94f,
        0.97f,
        1.0f,
        1.0f);
    const FLinearColor Accent(
        0.02f,
        0.72f,
        0.95f,
        1.0f);
    DrawText(
        FString::Printf(
            TEXT("%03d KM/H"),
            FMath::RoundToInt(State.SpeedKph)),
        Primary,
        Canvas->SizeX - 250.0f,
        Canvas->SizeY - 92.0f,
        GEngine ? GEngine->GetLargeFont() : nullptr);
    DrawText(
        State.bHandbraking
            ? TEXT("HANDBRAKE")
            : State.bBoosting
                ? TEXT("NITRO")
                : TEXT(""),
        Accent,
        42.0f,
        42.0f,
        GEngine ? GEngine->GetLargeFont() : nullptr);
    DrawRect(
        FLinearColor(0.02f, 0.02f, 0.02f, 0.9f),
        Canvas->SizeX - 250.0f,
        Canvas->SizeY - 122.0f,
        200.0f,
        12.0f);
    DrawRect(
        Accent,
        Canvas->SizeX - 248.0f,
        Canvas->SizeY - 120.0f,
        196.0f * State.NitroPercent,
        8.0f);
}

AAARacingUIGameMode::AAARacingUIGameMode()
{
    HUDClass = AAARacingUIHUD::StaticClass();
}
