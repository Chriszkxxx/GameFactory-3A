using UnrealBuildTool;

public class RacingUIExample : ModuleRules
{
    public RacingUIExample(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "RacingExample"
        });
    }
}
