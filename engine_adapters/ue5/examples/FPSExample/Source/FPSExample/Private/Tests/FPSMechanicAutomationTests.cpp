#include "FPSExample.h"

#include "Engine/DamageEvents.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAAFPSDamageStateTest,
    "A3Game.FPSExample.Mechanic.DamageState",
    EAutomationTestFlags::EditorContext
        | EAutomationTestFlags::EngineFilter)

bool FAAFPSDamageStateTest::RunTest(
    const FString& Parameters)
{
    AAAFPSCharacter* Character =
        NewObject<AAAFPSCharacter>();
    TestNotNull(TEXT("FPS character exists"), Character);
    if (!Character)
    {
        return false;
    }

    FDamageEvent DamageEvent;
    Character->TakeDamage(
        25.0f,
        DamageEvent,
        nullptr,
        nullptr);
    TestEqual(
        TEXT("Damage updates mechanic health"),
        Character->GetHealth(),
        75.0f);
    TestFalse(
        TEXT("Full magazine cannot reload"),
        Character->ReloadWeapon());
    TestEqual(
        TEXT("Contract schema version is stable"),
        FAAFPSMechanicState().ContractVersion,
        1);
    return true;
}

#endif
