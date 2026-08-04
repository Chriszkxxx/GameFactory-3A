using UnrealBuildTool;

public class ArenaFighterExample : ModuleRules
{
    public ArenaFighterExample(ReadOnlyTargetRules Target) : base(Target)
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
