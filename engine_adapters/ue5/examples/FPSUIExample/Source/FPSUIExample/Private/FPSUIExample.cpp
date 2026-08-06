#include "FPSUIExample.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "FPSMechanicContract.h"

IMPLEMENT_MODULE(FFPSUIExampleModule, FPSUIExample)

void AAAFPSUIHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas)
    {
        return;
    }

    UAAAFPSMechanicContractSubsystem* Contract =
        GetWorld()
            ? GetWorld()->GetSubsystem<
                UAAAFPSMechanicContractSubsystem>()
            : nullptr;
    if (!Contract)
    {
        return;
    }
    const FAAFPSMechanicState State =
        Contract->GetMechanicState();
    const float HealthPercent = State.PlayerMaxHealth > 0.0f
        ? FMath::Clamp(
            State.PlayerHealth / State.PlayerMaxHealth,
            0.0f,
            1.0f)
        : 0.0f;

    const float CenterX = Canvas->SizeX * 0.5f;
    const float CenterY = Canvas->SizeY * 0.5f;
    const FLinearColor Color(0.92f, 0.96f, 1.0f, 1.0f);
    DrawRect(
        Color,
        CenterX - 18.0f,
        CenterY - 1.0f,
        12.0f,
        2.0f);
    DrawRect(
        Color,
        CenterX + 6.0f,
        CenterY - 1.0f,
        12.0f,
        2.0f);
    DrawRect(
        Color,
        CenterX - 1.0f,
        CenterY - 18.0f,
        2.0f,
        12.0f);
    DrawRect(
        Color,
        CenterX - 1.0f,
        CenterY + 6.0f,
        2.0f,
        12.0f);

    DrawText(
        FString::Printf(
            TEXT("HEALTH %03d"),
            FMath::RoundToInt(HealthPercent * 100.0f)),
        Color,
        42.0f,
        Canvas->SizeY - 68.0f,
        GEngine ? GEngine->GetLargeFont() : nullptr);
    DrawText(
        FString::Printf(
            TEXT("%02d / %03d"),
            State.MagazineAmmo,
            State.ReserveAmmo),
        Color,
        Canvas->SizeX - 210.0f,
        Canvas->SizeY - 68.0f,
        GEngine ? GEngine->GetLargeFont() : nullptr);
}

AAAFPSUIGameMode::AAAFPSUIGameMode()
{
    HUDClass = AAAFPSUIHUD::StaticClass();
}
