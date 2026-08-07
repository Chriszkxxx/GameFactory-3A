#include "RacingExample.h"

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAAARacingDriveStateTest,
    "A3Game.RacingExample.Mechanic.DriveState",
    EAutomationTestFlags::EditorContext
        | EAutomationTestFlags::EngineFilter)

bool FAAARacingDriveStateTest::RunTest(
    const FString& Parameters)
{
    AAARacingPawn* Vehicle = NewObject<AAARacingPawn>();
    TestNotNull(TEXT("Racing vehicle exists"), Vehicle);
    if (!Vehicle)
    {
        return false;
    }

    Vehicle->ApplyDriveInput(0.0f, 1.0f, false, false);
    Vehicle->Tick(0.25f);
    TestTrue(
        TEXT("Throttle increases vehicle speed"),
        Vehicle->GetSpeedKph() > 0.0f);
    Vehicle->ResetVehicle();
    TestEqual(
        TEXT("Reset clears vehicle speed"),
        Vehicle->GetSpeedKph(),
        0.0f);
    TestEqual(
        TEXT("Contract schema version is stable"),
        FAAARacingMechanicState().ContractVersion,
        1);
    return true;
}

#endif
