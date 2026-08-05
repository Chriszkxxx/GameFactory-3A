using UnrealBuildTool;

public class FPSExample : ModuleRules
{
    public FPSExample(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "A3GamePlayable"
        });
    }
}
