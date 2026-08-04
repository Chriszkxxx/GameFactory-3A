using UnrealBuildTool;

public class RacingExample : ModuleRules
{
    public RacingExample(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "AAAGamePlayable"
        });
    }
}
