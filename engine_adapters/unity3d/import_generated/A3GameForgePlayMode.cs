// Generic Editor entry point for generated Unity projects.
// The project/scene is selected by UnityClient.runtime.launch_editor; this
// script only waits for the Editor to finish compiling and enters Play Mode.

using System;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class A3GameForgePlayMode
{
    private const string LaunchPendingKey = "A3GameForge.PlayMode.LaunchPending";
    private const string LaunchArgumentConsumedKey = "A3GameForge.PlayMode.ArgumentConsumed";

    static A3GameForgePlayMode()
    {
        bool unconsumedLaunchArgument = HasLaunchArgument() &&
            !SessionState.GetBool(LaunchArgumentConsumedKey, false);
        if (unconsumedLaunchArgument)
            SessionState.SetBool(LaunchArgumentConsumedKey, true);
        if (unconsumedLaunchArgument || SessionState.GetBool(LaunchPendingKey, false))
            EditorApplication.delayCall += ScheduleEnter;
    }

    public static void Enter()
    {
        SessionState.SetBool(LaunchArgumentConsumedKey, true);
        SessionState.SetBool(LaunchPendingKey, true);
        ScheduleEnter();
    }

    private static void ScheduleEnter()
    {
        EditorApplication.update -= EnterWhenReady;
        EditorApplication.update += EnterWhenReady;
        Debug.Log("[A3GameForgePlayMode] Waiting for Unity Editor compilation");
    }

    private static void EnterWhenReady()
    {
        if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            return;

        EditorApplication.update -= EnterWhenReady;
        SessionState.SetBool(LaunchPendingKey, false);
        if (EditorApplication.isPlayingOrWillChangePlaymode)
            return;

        Debug.Log("[A3GameForgePlayMode] Entering Play Mode");
        EditorApplication.isPlaying = true;
    }

    private static bool HasLaunchArgument()
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int index = 0; index + 1 < args.Length; index++)
        {
            if (args[index] == "-executeMethod" &&
                args[index + 1] == "A3GameForgePlayMode.Enter")
                return true;
        }
        return false;
    }
}
