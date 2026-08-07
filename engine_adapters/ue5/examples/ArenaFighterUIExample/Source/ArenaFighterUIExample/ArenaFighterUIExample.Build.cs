using UnrealBuildTool;

public class ArenaFighterUIExample : ModuleRules
{
    public ArenaFighterUIExample(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "ArenaFighterExample"
        });
    }
}
