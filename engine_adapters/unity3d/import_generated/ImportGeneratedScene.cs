// engine_adapters/unity3d/import_generated/ImportGeneratedScene.cs
//
// Builds a Unity scene from a scene-description JSON: an array of instances,
// each specifying a prefab path and a TRS transform (position / rotation /
// scale). The scene is saved as a .unity asset and optionally added to the
// build settings.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod ImportGeneratedScene.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to scene_report.json>
//
// job.json keys: src, dest, world_id, project_id, publish, replace_existing
//
// The scene-description JSON (pointed to by job 'src') is an array:
//     [
//       { "prefab": "Assets/Generated/Prefabs/Tree.prefab",
//         "position": [0, 0, 0],
//         "rotation": [0, 0, 0, 1],
//         "scale":    [1, 1, 1] },
//       ...
//     ]

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class ImportGeneratedScene
{
    [Serializable]
    public class SceneReport
    {
        public bool ok;
        public string scenePath = "";
        public int instanceCount;
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    [Serializable]
    public class SceneInstance
    {
        public string prefab = "";
        public float[] position;
        public float[] rotation;
        public float[] scale;
    }

    [Serializable]
    public class SceneInstanceList
    {
        public List<SceneInstance> instances = new List<SceneInstance>();
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new SceneReport();
        string reportPath = Get(args, "report", null);

        try
        {
            string src = GetJobValue(args, "src", null);
            if (string.IsNullOrEmpty(src))
                throw new ArgumentException("job 'src' (path to scene description JSON) is required");

            report = BuildScene(
                src,
                GetJobValue(args, "dest", "Assets/Generated/Scenes"),
                GetJobValue(args, "world_id", ""),
                GetJobValue(args, "project_id", ""),
                GetJobValue(args, "publish", "false"),
                GetJobValue(args, "replace_existing", "true")
            );
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[ImportGeneratedScene] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Build scene ───────────────────────────────────────────────────────────

    /// <summary>
    /// Read a scene-description JSON, instantiate prefabs at their transforms,
    /// and save the result as a .unity scene asset.
    /// </summary>
    /// <param name="srcPath">Absolute path to the scene-description JSON.</param>
    /// <param name="destFolder">Project-relative folder for the scene asset.</param>
    /// <param name="worldId">World identifier; used for the scene file name.</param>
    /// <param name="projectId">Project identifier (stored in the root GameObject name).</param>
    /// <param name="publish">"true" to add the scene to EditorBuildSettings.</param>
    /// <param name="replaceExisting">"true" to overwrite an existing scene file.</param>
    public static SceneReport BuildScene(
        string srcPath,
        string destFolder = "Assets/Generated/Scenes",
        string worldId = "",
        string projectId = "",
        string publish = "false",
        string replaceExisting = "true")
    {
        var report = new SceneReport();

        if (!File.Exists(srcPath))
            throw new FileNotFoundException("scene description JSON not found", srcPath);

        // 1. Parse the scene-description JSON. JsonUtility cannot handle a
        //    top-level array, so wrap it in an object before deserializing.
        string sceneJson = File.ReadAllText(srcPath);
        string trimmed = sceneJson.TrimStart();
        if (trimmed.StartsWith("["))
            sceneJson = "{\"instances\":" + sceneJson + "}";

        SceneInstanceList data;
        try
        {
            data = JsonUtility.FromJson<SceneInstanceList>(sceneJson);
        }
        catch (Exception e)
        {
            throw new InvalidOperationException(
                $"failed to parse scene JSON from {srcPath}: {e.Message}");
        }

        if (data == null || data.instances == null || data.instances.Count == 0)
        {
            report.warnings.Add("scene JSON contains no instances; creating empty scene");
            data = data ?? new SceneInstanceList();
            if (data.instances == null) data.instances = new List<SceneInstance>();
        }

        // 2. Create a new empty scene.
        var scene = EditorSceneManager.NewScene(
            NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // Root GameObject to hold all instances; keeps the hierarchy clean and
        // gives the scene a discoverable anchor.
        string rootName = string.IsNullOrEmpty(worldId)
            ? "GeneratedWorld"
            : $"World_{worldId}";
        if (!string.IsNullOrEmpty(projectId))
            rootName += $"_proj_{projectId}";
        var root = new GameObject(SanitizeName(rootName));

        // 3. Instantiate each prefab at its specified TRS transform.
        int count = 0;
        for (int i = 0; i < data.instances.Count; i++)
        {
            var inst = data.instances[i];
            if (string.IsNullOrEmpty(inst.prefab))
            {
                report.warnings.Add($"instance {i}: empty prefab path, skipped");
                continue;
            }

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(inst.prefab);
            if (prefab == null)
            {
                report.warnings.Add($"instance {i}: prefab not found at '{inst.prefab}', skipped");
                continue;
            }

            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
            go.transform.SetParent(root.transform, worldPositionStays: false);
            go.name = $"{prefab.name}_{i:000}";

            // Apply TRS if provided. Unity's coordinate system is Y-up, metric —
            // same as glTF, so no axis conversion is needed.
            if (inst.position != null && inst.position.Length >= 3)
                go.transform.localPosition = new Vector3(
                    inst.position[0], inst.position[1], inst.position[2]);

            if (inst.rotation != null && inst.rotation.Length >= 4)
                go.transform.localRotation = new Quaternion(
                    inst.rotation[0], inst.rotation[1],
                    inst.rotation[2], inst.rotation[3]);

            if (inst.scale != null && inst.scale.Length >= 3)
                go.transform.localScale = new Vector3(
                    inst.scale[0], inst.scale[1], inst.scale[2]);

            count++;
        }

        report.instanceCount = count;

        // 4. Save the scene asset.
        Directory.CreateDirectory(destFolder);
        string sceneName = string.IsNullOrEmpty(worldId)
            ? "GeneratedScene"
            : $"World_{worldId}";
        sceneName = SanitizeName(sceneName);
        string scenePath = $"{destFolder}/{sceneName}.unity";

        bool replace = string.Equals(replaceExisting, "true", StringComparison.OrdinalIgnoreCase);
        if (File.Exists(scenePath) && !replace)
        {
            report.warnings.Add(
                $"scene {scenePath} already exists and replace_existing=false; saving as copy");
            scenePath = AssetDatabase.GenerateUniqueAssetPath(scenePath);
        }
        else if (File.Exists(scenePath))
        {
            report.warnings.Add($"replaced existing scene {scenePath}");
        }

        EditorSceneManager.SaveScene(scene, scenePath);
        report.scenePath = scenePath;

        // 5. Optionally publish: add the scene to EditorBuildSettings so it is
        //    included in builds.
        if (string.Equals(publish, "true", StringComparison.OrdinalIgnoreCase))
        {
            var buildScenes = new List<EditorBuildSettingsScene>(
                EditorBuildSettings.scenes);
            bool found = false;
            foreach (var bs in buildScenes)
            {
                if (bs.path == scenePath) { found = true; break; }
            }
            if (!found)
            {
                buildScenes.Add(new EditorBuildSettingsScene(scenePath, true));
                EditorBuildSettings.scenes = buildScenes.ToArray();
                report.warnings.Add($"added {scenePath} to EditorBuildSettings");
            }
        }

        AssetDatabase.SaveAssets();
        report.ok = true;
        Debug.Log($"[ImportGeneratedScene] {report.scenePath}  " +
                  $"instances={report.instanceCount}  warnings={report.warnings.Count}");
        return report;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    static Dictionary<string, string> ParseArgs(string[] argv)
    {
        var args = new Dictionary<string, string>();
        for (int i = 0; i < argv.Length; i++)
        {
            if (!argv[i].StartsWith("--")) continue;
            string key = argv[i].Substring(2);
            string value = (i + 1 < argv.Length && !argv[i + 1].StartsWith("--"))
                ? argv[++i] : "";
            args[key] = value;
        }
        return args;
    }

    static string Get(Dictionary<string, string> args, string key, string fallback)
    {
        if (args.TryGetValue(key, out var v) && !string.IsNullOrEmpty(v)) return v;
        return A3GameForgeEditorBridge.GetArgument(key, fallback);
    }

    static string GetJobValue(Dictionary<string, string> args, string key, string fallback = "")
    {
        string jobPath = Get(args, "job", null);
        if (jobPath != null && File.Exists(jobPath))
        {
            string json = File.ReadAllText(jobPath);
            string pattern = "\"" + key + "\"";
            int idx = json.IndexOf(pattern, StringComparison.OrdinalIgnoreCase);
            if (idx >= 0)
            {
                int colonIdx = json.IndexOf(':', idx + pattern.Length);
                if (colonIdx >= 0)
                {
                    int start = json.IndexOf('"', colonIdx + 1);
                    if (start >= 0)
                    {
                        int end = json.IndexOf('"', start + 1);
                        if (end > start) return json.Substring(start + 1, end - start - 1);
                    }
                    // Try non-string value (bool/number)
                    int valueStart = colonIdx + 1;
                    while (valueStart < json.Length && (json[valueStart] == ' ' || json[valueStart] == '\t')) valueStart++;
                    int valueEnd = valueStart;
                    while (valueEnd < json.Length && json[valueEnd] != ',' && json[valueEnd] != '}' && json[valueEnd] != '\n') valueEnd++;
                    return json.Substring(valueStart, valueEnd - valueStart).Trim();
                }
            }
        }
        return Get(args, key, fallback);
    }

    static void WriteReport(object report, string reportPath)
    {
        string json = JsonUtility.ToJson(report, prettyPrint: true);
        if (!string.IsNullOrEmpty(reportPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(reportPath)));
            File.WriteAllText(reportPath, json);
        }
        Debug.Log("[ImportGeneratedScene] report " + json);
    }

    static string SanitizeName(string name)
    {
        foreach (char c in Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
        return name.Replace(' ', '_');
    }
}
