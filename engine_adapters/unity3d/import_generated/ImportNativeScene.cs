// engine_adapters/unity3d/import_generated/ImportNativeScene.cs
//
// Imports a native Unity .unity scene file (and its asset dependencies) into
// a project. Mirrors UE5's native_map import: copies the scene + all sibling
// assets, refreshes AssetDatabase, opens the scene, and reports metadata.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod ImportNativeScene.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to scene_report.json>
//
// job.json keys:
//   src              — absolute path to a .unity file OR a directory containing
//                      .unity files (the directory is treated as a content pack)
//   dest             — project-relative destination folder (default: Assets/Imported/Scenes)
//   native_scene     — name of the main .unity scene to select (optional; if
//                      omitted, the largest .unity file is chosen)
//   world_id         — world identifier (stored in metadata)
//   project_id       — project identifier (stored in metadata)
//   publish          — "true" to add the scene to EditorBuildSettings
//   replace_existing — "true" to overwrite existing files

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class ImportNativeScene
{
    [Serializable]
    public class NativeSceneReport
    {
        public bool ok;
        public string scenePath = "";
        public int sceneCount;
        public int assetCount;
        public int copiedFiles;
        public int reusedFiles;
        public string cameraInfo = "";
        public string spawnPoint = "";
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new NativeSceneReport();
        string reportPath = Get(args, "report", null);

        try
        {
            report = Import(
                GetJobValue(args, "src", null),
                GetJobValue(args, "dest", "Assets/Imported/Scenes"),
                GetJobValue(args, "native_scene", ""),
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
            Debug.LogError("[ImportNativeScene] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Import ────────────────────────────────────────────────────────────────

    public static NativeSceneReport Import(
        string srcPath,
        string destFolder = "Assets/Imported/Scenes",
        string nativeScene = "",
        string worldId = "",
        string projectId = "",
        string publish = "false",
        string replaceExisting = "true")
    {
        var report = new NativeSceneReport();

        if (string.IsNullOrEmpty(srcPath))
            throw new ArgumentException("src is required: path to .unity file or directory");

        string absSrc = Path.GetFullPath(srcPath);
        bool replace = string.Equals(replaceExisting, "true", StringComparison.OrdinalIgnoreCase);

        // 1. Resolve source scene files and asset directory.
        List<string> sourceSceneFiles;
        string sourceRoot;

        if (Directory.Exists(absSrc))
        {
            // Directory mode: find all .unity files, copy the whole tree.
            sourceRoot = absSrc;
            sourceSceneFiles = new List<string>(
                Directory.GetFiles(absSrc, "*.unity", SearchOption.AllDirectories));
            if (sourceSceneFiles.Count == 0)
                throw new InvalidOperationException(
                    $"no .unity scene files found in directory: {absSrc}");
        }
        else if (File.Exists(absSrc) &&
                 absSrc.EndsWith(".unity", StringComparison.OrdinalIgnoreCase))
        {
            // Single file mode: copy the scene + sibling assets.
            sourceRoot = Path.GetDirectoryName(absSrc);
            sourceSceneFiles = new List<string> { absSrc };
        }
        else
        {
            throw new FileNotFoundException(
                $"source must be a .unity file or a directory containing .unity files: {absSrc}");
        }

        report.sceneCount = sourceSceneFiles.Count;

        // 2. Copy assets into the project.
        string projectRoot = Directory.GetCurrentDirectory();
        string destAbs = Path.Combine(projectRoot, destFolder);
        Directory.CreateDirectory(destAbs);

        int copied = 0;
        int reused = 0;
        var scenePaths = new List<string>();

        // Copy all recognized asset files (preserving directory structure).
        var assetExtensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".unity", ".prefab", ".mat", ".png", ".jpg", ".jpeg", ".tga",
            ".fbx", ".obj", ".glb", ".gltf", ".wav", ".mp3", ".ogg",
            ".controller", ".anim", ".overrideController", ".asmdef",
            ".cs", ".shader", ".cginc", ".hlsl", ".renderTexture",
            ".physicMaterial", ".mesh", ".asset", ".lighting", ".exr", ".json",
            ".bytes", ".txt", ".shadergraph", ".vfx"
        };

        foreach (string sourceFile in EnumerateFilesSafe(sourceRoot))
        {
            string ext = Path.GetExtension(sourceFile);
            // Keep every .meta file, including folder metadata.  Unity GUIDs
            // inside scenes/materials/textures depend on these files and
            // regenerating them breaks references after import.
            bool isMeta = sourceFile.EndsWith(".meta", StringComparison.OrdinalIgnoreCase);
            if (!isMeta && !assetExtensions.Contains(ext))
                continue;

            string relative = Path.GetRelativePath(sourceRoot, sourceFile);
            string targetFile = Path.Combine(destAbs, relative);
            string targetDir = Path.GetDirectoryName(targetFile);
            Directory.CreateDirectory(targetDir);

            string targetProjectRelative =
                Path.Combine(destFolder, relative).Replace('\\', '/');

            if (File.Exists(targetFile) && !replace)
            {
                if (File.ReadAllBytes(targetFile).Length == File.ReadAllBytes(sourceFile).Length)
                    reused++;
                else
                    report.warnings.Add($"skipped (exists, not replacing): {relative}");
                continue;
            }

            File.Copy(sourceFile, targetFile, overwrite: true);
            copied++;

            if (ext.Equals(".unity", StringComparison.OrdinalIgnoreCase))
                scenePaths.Add(targetProjectRelative);
        }

        report.copiedFiles = copied;
        report.reusedFiles = reused;
        report.assetCount = copied + reused;

        // 3. Refresh AssetDatabase so Unity imports everything.
        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
        AssetDatabase.SaveAssets();

        // 4. Select the main scene.
        string selectedScenePath = SelectScene(scenePaths, nativeScene);
        if (string.IsNullOrEmpty(selectedScenePath))
        {
            report.warnings.Add("no .unity scene was copied; cannot open");
            report.ok = true;
            return report;
        }

        report.scenePath = selectedScenePath;

        // 5. Open the scene and extract metadata.
        var scene = EditorSceneManager.OpenScene(
            selectedScenePath, OpenSceneMode.Single);

        // Camera info. Scene has no GetMainCamera helper in Unity 2022.3;
        // inspect the loaded scene roots so this remains valid in batchmode
        // and does not depend on whichever editor scene was active before.
        Camera cam = null;
        foreach (GameObject root in scene.GetRootGameObjects())
        {
            cam = root.GetComponentInChildren<Camera>(true);
            if (cam != null) break;
        }
        if (cam != null)
        {
            var pos = cam.transform.position;
            var rot = cam.transform.eulerAngles;
            report.cameraInfo = $"pos=({pos.x:F1},{pos.y:F1},{pos.z:F1}) " +
                               $"rot=({rot.x:F0},{rot.y:F0},{rot.z:F0})";
        }
        else
        {
            report.warnings.Add("no Camera found in scene");
        }

        // Spawn point: look for a GameObject named "PlayerStart" or "SpawnPoint"
        string spawnInfo = FindSpawnPoint(scene);
        report.spawnPoint = spawnInfo;

        // Count GameObjects for the report
        int goCount = scene.rootCount;
        report.warnings.Add($"scene has {goCount} root GameObjects");

        // 6. Optionally publish: add to EditorBuildSettings.
        if (string.Equals(publish, "true", StringComparison.OrdinalIgnoreCase))
        {
            var buildScenes = new List<EditorBuildSettingsScene>(
                EditorBuildSettings.scenes);
            bool found = false;
            foreach (var bs in buildScenes)
            {
                if (bs.path == selectedScenePath) { found = true; break; }
            }
            if (!found)
            {
                buildScenes.Add(new EditorBuildSettingsScene(selectedScenePath, true));
                EditorBuildSettings.scenes = buildScenes.ToArray();
                report.warnings.Add($"added {selectedScenePath} to EditorBuildSettings");
            }
        }

        report.ok = true;
        Debug.Log($"[ImportNativeScene] {report.scenePath}  " +
                  $"scenes={report.sceneCount}  assets={report.assetCount}  " +
                  $"warnings={report.warnings.Count}");
        return report;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    static string SelectScene(List<string> scenePaths, string nativeScene)
    {
        if (scenePaths.Count == 0)
            return null;

        if (!string.IsNullOrEmpty(nativeScene))
        {
            string requested = nativeScene.Trim();
            string requestedLower = requested.ToLowerInvariant();
            // Try exact match, then filename match
            foreach (string path in scenePaths)
            {
                if (path.Equals(requested, StringComparison.OrdinalIgnoreCase))
                    return path;
            }
            foreach (string path in scenePaths)
            {
                string name = Path.GetFileNameWithoutExtension(path);
                if (name.Equals(requested, StringComparison.OrdinalIgnoreCase))
                    return path;
            }
            foreach (string path in scenePaths)
            {
                if (path.ToLowerInvariant().Contains(requestedLower))
                    return path;
            }
            Debug.LogWarning(
                $"[ImportNativeScene] native_scene '{requested}' not found; " +
                $"available: {string.Join(", ", scenePaths)}");
        }

        // Default: prefer "Main" or "Demo" scene, then largest file
        scenePaths.Sort((a, b) =>
        {
            int scoreA = 0, scoreB = 0;
            string nameA = Path.GetFileNameWithoutExtension(a).ToLowerInvariant();
            string nameB = Path.GetFileNameWithoutExtension(b).ToLowerInvariant();
            if (nameA == "main") scoreA += 100;
            if (nameA == "demo") scoreA += 50;
            if (nameB == "main") scoreB += 100;
            if (nameB == "demo") scoreB += 50;
            if (scoreA != scoreB) return scoreB - scoreA;
            // Fall back to file size
            long sizeA = File.Exists(a) ? new FileInfo(a).Length : 0;
            long sizeB = File.Exists(b) ? new FileInfo(b).Length : 0;
            return sizeB.CompareTo(sizeA);
        });
        return scenePaths[0];
    }

    static string FindSpawnPoint(Scene scene)
    {
        var roots = scene.GetRootGameObjects();
        foreach (var go in roots)
        {
            // Check name
            string name = go.name;
            if (name.Equals("PlayerStart", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("SpawnPoint", StringComparison.OrdinalIgnoreCase) ||
                name.Equals("PlayerSpawn", StringComparison.OrdinalIgnoreCase))
            {
                var pos = go.transform.position;
                var rot = go.transform.eulerAngles;
                return $"name={name} pos=({pos.x:F1},{pos.y:F1},{pos.z:F1}) " +
                       $"rot=({rot.x:F0},{rot.y:F0},{rot.z:F0})";
            }
            // Check children
            var children = go.GetComponentsInChildren<Transform>(true);
            foreach (var child in children)
            {
                string childName = child.name;
                if (childName.Equals("PlayerStart", StringComparison.OrdinalIgnoreCase) ||
                    childName.Equals("SpawnPoint", StringComparison.OrdinalIgnoreCase) ||
                    childName.Equals("PlayerSpawn", StringComparison.OrdinalIgnoreCase))
                {
                    var pos = child.position;
                    var rot = child.eulerAngles;
                    return $"name={childName} pos=({pos.x:F1},{pos.y:F1},{pos.z:F1}) " +
                           $"rot=({rot.x:F0},{rot.y:F0},{rot.z:F0})";
                }
            }
        }
        return "";
    }

    static IEnumerable<string> EnumerateFilesSafe(string root)
    {
        // Skip Unity meta files, Library, Temp, obj, bin
        var skipDirs = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "Library", "Temp", "obj", "bin", ".git", "node_modules",
            "ProjectSettings", "Packages", "Logs"
        };
        var stack = new Stack<string>();
        stack.Push(root);
        while (stack.Count > 0)
        {
            string current = stack.Pop();
            foreach (string dir in Directory.GetDirectories(current))
            {
                string dirName = Path.GetFileName(dir);
                if (skipDirs.Contains(dirName))
                    continue;
                stack.Push(dir);
            }
            foreach (string file in Directory.GetFiles(current))
            {
                yield return file;
            }
        }
    }

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
        return GameFactory3AEditorBridge.GetArgument(key, fallback);
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
        Debug.Log("[ImportNativeScene] report " + json);
        if (!string.IsNullOrEmpty(reportPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(reportPath)));
            File.WriteAllText(reportPath, json);
        }
    }
}
