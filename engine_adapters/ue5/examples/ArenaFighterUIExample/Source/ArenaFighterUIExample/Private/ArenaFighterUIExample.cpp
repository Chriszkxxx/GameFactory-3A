#include "ArenaFighterUIExample.h"

#include "ArenaFighterMechanicContract.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

IMPLEMENT_MODULE(
    FArenaFighterUIExampleModule,
    ArenaFighterUIExample)

void AAAArenaFighterUIHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas)
    {
        return;
    }

    UAAArenaFighterMechanicContractSubsystem* Contract =
        GetWorld()
            ? GetWorld()->GetSubsystem<
                UAAArenaFighterMechanicContractSubsystem>()
            : nullptr;
    if (!Contract)
    {
        return;
    }
    const FAAArenaFighterMechanicState State =
        Contract->GetMechanicState();
    const float PlayerHealthPercent =
        State.PlayerMaxHealth > 0.0f
        ? FMath::Clamp(
            State.PlayerHealth / State.PlayerMaxHealth,
            0.0f,
            1.0f)
        : 0.0f;
    const float OpponentHealthPercent =
        State.OpponentMaxHealth > 0.0f
        ? FMath::Clamp(
            State.OpponentHealth / State.OpponentMaxHealth,
            0.0f,
            1.0f)
        : 0.0f;

    const float Width = FMath::Clamp(
        Canvas->SizeX * 0.32f,
        260.0f,
        520.0f);
    DrawHealthBar(
        TEXT("PLAYER"),
        PlayerHealthPercent,
        48.0f,
        48.0f,
        Width,
        FLinearColor(0.1f, 0.75f, 0.3f, 1.0f));
    DrawHealthBar(
        TEXT("OPPONENT"),
        OpponentHealthPercent,
        Canvas->SizeX - Width - 48.0f,
        48.0f,
        Width,
        FLinearColor(0.9f, 0.18f, 0.12f, 1.0f));
}

void AAAArenaFighterUIHUD::DrawHealthBar(
    const FString& Label,
    float HealthPercent,
    float X,
    float Y,
    float Width,
    const FLinearColor& Color)
{
    DrawText(
        Label,
        FLinearColor::White,
        X,
        Y - 24.0f,
        GEngine ? GEngine->GetSmallFont() : nullptr);
    DrawRect(
        FLinearColor(0.02f, 0.02f, 0.02f, 0.9f),
        X,
        Y,
        Width,
        24.0f);
    DrawRect(
        Color,
        X + 3.0f,
        Y + 3.0f,
        (Width - 6.0f)
            * FMath::Clamp(HealthPercent, 0.0f, 1.0f),
        18.0f);
}

AAAArenaFighterUIGameMode::AAAArenaFighterUIGameMode()
{
    HUDClass = AAAArenaFighterUIHUD::StaticClass();
}
