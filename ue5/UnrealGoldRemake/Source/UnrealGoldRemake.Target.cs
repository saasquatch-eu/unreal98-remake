using UnrealBuildTool;

public class UnrealGoldRemakeTarget : TargetRules
{
    public UnrealGoldRemakeTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("UnrealGoldRemake");
    }
}
