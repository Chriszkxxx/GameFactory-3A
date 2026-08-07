using UnrealBuildTool;

public class A3GamePlayable : ModuleRules
{
    public A3GamePlayable(ReadOnlyTargetRules Target) : base(Target)
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
