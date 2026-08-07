using UnrealBuildTool;

public class FPSUIExample : ModuleRules
{
    public FPSUIExample(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "FPSExample"
        });
    }
}
