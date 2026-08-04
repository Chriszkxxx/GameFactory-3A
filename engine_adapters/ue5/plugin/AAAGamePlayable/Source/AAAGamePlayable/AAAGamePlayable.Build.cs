using UnrealBuildTool;

public class AAAGamePlayable : ModuleRules
{
    public AAAGamePlayable(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core",
            "CoreUObject",
            "Engine"
        });

        PrivateDependencyModuleNames.AddRange(new[]
        {
            "Json",
            "Networking",
            "Sockets"
        });
    }
}
