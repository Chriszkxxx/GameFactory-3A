// Builds a real Unity player and reports the BuildPipeline result.
// Editor script: installed automatically in <project>/Assets/Editor.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class BuildPlayer
{
    [Serializable]
    private class BuildJob
    {
        public string target = "StandaloneWindows64";
        public string output_path = "";
        public string configuration = "Development";
        public bool clean;
        public string[] scenes;
    }

    [Serializable]
    private class BuildPlayerReport
    {
        public bool ok;
        public string result = "";
        public string target = "";
        public string outputPath = "";
        public ulong totalSize;
        public int totalErrors;
        public int totalWarnings;
        public double totalSeconds;
        public string[] scenes;
        public string error = "";
    }

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        string reportPath = Get(args, "report", "");
        var result = new BuildPlayerReport();

        try
        {
            var job = ReadJob(Get(args, "job", ""));
            if (!Enum.TryParse(job.target, true, out BuildTarget target))
                throw new ArgumentException("Unsupported Unity BuildTarget: " + job.target);
            if (string.IsNullOrWhiteSpace(job.output_path))
                throw new ArgumentException("output_path is required");

            string[] scenes = job.scenes != null && job.scenes.Length > 0
                ? job.scenes.Where(path => !string.IsNullOrWhiteSpace(path)).ToArray()
                : EditorBuildSettings.scenes
                    .Where(scene => scene.enabled)
                    .Select(scene => scene.path)
                    .ToArray();
            if (scenes.Length == 0)
                scenes = new[] { CreateBootstrapScene() };

            foreach (string scene in scenes)
            {
                if (AssetDatabase.LoadAssetAtPath<SceneAsset>(scene) == null)
                    throw new FileNotFoundException("Build scene was not found", scene);
            }

            string output = Path.GetFullPath(job.output_path);
            string parent = target == BuildTarget.WebGL
                ? output
                : Path.GetDirectoryName(output);
            if (!string.IsNullOrEmpty(parent))
                Directory.CreateDirectory(parent);
            if (job.clean)
                CleanOutput(output, target);

            BuildOptions options = BuildOptions.None;
            if (string.Equals(job.configuration, "Development", StringComparison.OrdinalIgnoreCase))
                options |= BuildOptions.Development;

            var build = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = output,
                target = target,
                options = options,
            });
            var summary = build.summary;
            result.ok = summary.result == BuildResult.Succeeded;
            result.result = summary.result.ToString();
            result.target = summary.platform.ToString();
            result.outputPath = output;
            result.totalSize = summary.totalSize;
            result.totalErrors = summary.totalErrors;
            result.totalWarnings = summary.totalWarnings;
            result.totalSeconds = summary.totalTime.TotalSeconds;
            result.scenes = scenes;
            if (!result.ok)
                result.error = "BuildPipeline.BuildPlayer returned " + summary.result;
        }
        catch (Exception exception)
        {
            result.ok = false;
            result.error = exception.ToString();
            Debug.LogError("[BuildPlayer] " + exception);
        }

        WriteReport(result, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(result.ok ? 0 : 1);
    }

    private static string CreateBootstrapScene()
    {
        const string scenePath = "Assets/Scenes/A3GameBootstrap.unity";
        Directory.CreateDirectory("Assets/Scenes");
        Scene scene = EditorSceneManager.NewScene(
            NewSceneSetup.DefaultGameObjects,
            NewSceneMode.Single);

        Type bootstrapType = AppDomain.CurrentDomain.GetAssemblies()
            .Select(assembly => assembly.GetType("A3Game.A3GameBootstrap", false))
            .FirstOrDefault(type => type != null && typeof(Component).IsAssignableFrom(type));
        if (bootstrapType == null)
            throw new TypeLoadException("A3Game.A3GameBootstrap was not compiled");

        var bootstrap = new GameObject("A3GameBootstrap");
        bootstrap.AddComponent(bootstrapType);
        if (!EditorSceneManager.SaveScene(scene, scenePath))
            throw new IOException("Unity could not save the bootstrap scene");
        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene(scenePath, true),
        };
        AssetDatabase.SaveAssets();
        return scenePath;
    }

    private static void CleanOutput(string output, BuildTarget target)
    {
        if (target == BuildTarget.WebGL || Directory.Exists(output))
        {
            if (Directory.Exists(output))
                Directory.Delete(output, true);
            return;
        }
        if (File.Exists(output))
            File.Delete(output);
    }

    private static BuildJob ReadJob(string path)
    {
        if (string.IsNullOrEmpty(path) || !File.Exists(path))
            throw new FileNotFoundException("Build job file was not found", path);
        var job = JsonUtility.FromJson<BuildJob>(File.ReadAllText(path));
        if (job == null)
            throw new InvalidDataException("Build job JSON is invalid");
        return job;
    }

    private static Dictionary<string, string> ParseArgs(string[] argv)
    {
        var parsed = new Dictionary<string, string>();
        for (int index = 0; index < argv.Length; index++)
        {
            if (!argv[index].StartsWith("--")) continue;
            string key = argv[index].Substring(2);
            string value = index + 1 < argv.Length && !argv[index + 1].StartsWith("--")
                ? argv[++index]
                : "";
            parsed[key] = value;
        }
        return parsed;
    }

    private static string Get(Dictionary<string, string> args, string key, string fallback)
    {
        return args.TryGetValue(key, out string value) && !string.IsNullOrEmpty(value)
            ? value
            : fallback;
    }

    private static void WriteReport(object report, string path)
    {
        string json = JsonUtility.ToJson(report, true);
        if (!string.IsNullOrEmpty(path))
        {
            string parent = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.WriteAllText(path, json);
        }
        Debug.Log("[BuildPlayer] report " + json);
    }
}
