#include "ArenaFighterExample.h"

#include "Engine/DamageEvents.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAAArenaFighterDamageStateTest,
    "A3Game.ArenaFighterExample.Mechanic.DamageState",
    EAutomationTestFlags::EditorContext
        | EAutomationTestFlags::EngineFilter)

bool FAAArenaFighterDamageStateTest::RunTest(
    const FString& Parameters)
{
    AAAArenaFighterCharacter* Fighter =
        NewObject<AAAArenaFighterCharacter>();
    TestNotNull(TEXT("Arena fighter exists"), Fighter);
    if (!Fighter)
    {
        return false;
    }

    FDamageEvent DamageEvent;
    Fighter->TakeDamage(
        100.0f,
        DamageEvent,
        nullptr,
        nullptr);
    TestTrue(
        TEXT("Lethal damage defeats the fighter"),
        Fighter->IsDefeated());
    TestEqual(
        TEXT("Defeated fighter health is zero"),
        Fighter->GetHealth(),
        0.0f);
    TestEqual(
        TEXT("Contract schema version is stable"),
        FAAArenaFighterMechanicState().ContractVersion,
        1);
    return true;
}

#endif
