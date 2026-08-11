// engine_adapters/unity3d/import_generated/ImportGeneratedAvatar.cs
//
// Imports a skeletal mesh (FBX / GLB) and configures a Humanoid avatar on it,
// then saves a prefab with an Animator bound to that avatar.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod ImportGeneratedAvatar.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to avatar_report.json>
//
// job.json keys: src, dest, name

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportGeneratedAvatar
{
    [Serializable]
    public class AvatarReport
    {
        public bool ok;
        public string assetPath = "";
        public string prefabPath = "";
        public string avatarPath = "";
        public bool hasHumanoidAvatar;
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new AvatarReport();
        string reportPath = Get(args, "report", null);

        try
        {
            string src = GetJobValue(args, "src", null);
            if (string.IsNullOrEmpty(src))
                throw new ArgumentException("job 'src' (path to skeletal mesh .fbx/.glb) is required");

            report = Import(
                src,
                GetJobValue(args, "dest", "Assets/Generated/Avatars"),
                GetJobValue(args, "name", null)
            );
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[ImportGeneratedAvatar] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Import ────────────────────────────────────────────────────────────────

    /// <summary>
    /// Copy a skeletal mesh into the project, configure the ModelImporter for
    /// Humanoid avatar creation, and save a prefab with an Animator.
    /// </summary>
    /// <param name="srcPath">Absolute path to the generated skeletal mesh file.</param>
    /// <param name="destFolder">Project-relative folder, e.g. Assets/Generated/Avatars.</param>
    /// <param name="assetName">Asset base name; defaults to the source file name.</param>
    public static AvatarReport Import(
        string srcPath,
        string destFolder = "Assets/Generated/Avatars",
        string assetName = null)
    {
        var report = new AvatarReport();

        if (!File.Exists(srcPath))
            throw new FileNotFoundException("skeletal mesh not found", srcPath);

        string ext = Path.GetExtension(srcPath).ToLowerInvariant();
        if (ext != ".fbx" && ext != ".glb" && ext != ".gltf")
            report.warnings.Add($"unusual extension {ext}; Humanoid avatar setup expects .fbx/.glb");

        if (string.IsNullOrEmpty(assetName))
            assetName = SanitizeName(Path.GetFileNameWithoutExtension(srcPath));

        // 1. Copy into the project so Unity can import it.
        Directory.CreateDirectory(destFolder);
        string assetPath = $"{destFolder}/{assetName}{ext}";
        CopyReplace(srcPath, assetPath);
        AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
        AssetDatabase.Refresh();
        report.assetPath = assetPath;

        // 2. Configure Humanoid avatar via ModelImporter.
        var importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
        if (importer == null)
            throw new InvalidOperationException($"no ModelImporter for {assetPath}");

        importer.animationType = ModelImporterAnimationType.Human;
        importer.SaveAndReimport();
        AssetDatabase.Refresh();

        // 3. Locate the generated Avatar sub-asset. Unity creates it as a
        //    sub-asset of the model during Humanoid import.
        Avatar avatar = null;
        var subAssets = AssetDatabase.LoadAllAssetsAtPath(assetPath);
        foreach (var sub in subAssets)
        {
            if (sub is Avatar av) { avatar = av; break; }
        }

        if (avatar != null)
        {
            report.hasHumanoidAvatar = avatar.isHuman;
            report.avatarPath = assetPath; // avatar is a sub-asset at the same path
            if (!avatar.isHuman)
                report.warnings.Add(
                    "avatar imported but isHuman is false; the skeleton may not " +
                    "match the Unity Humanoid bone mapping");
        }
        else
        {
            report.hasHumanoidAvatar = false;
            report.warnings.Add(
                "no Avatar sub-asset found after Humanoid import; check that the " +
                "skeleton matches Unity Humanoid requirements");
        }

        // 4. Instantiate, attach an Animator bound to the avatar, save prefab.
        var imported = AssetDatabase.LoadMainAssetAtPath(assetPath) as GameObject;
        if (imported == null)
            throw new InvalidOperationException($"Unity produced no GameObject for {assetPath}");

        var instance = (GameObject)PrefabUtility.InstantiatePrefab(imported);
        try
        {
            var animator = instance.GetComponent<Animator>() ?? instance.AddComponent<Animator>();
            if (avatar != null)
                animator.avatar = avatar;

            string prefabFolder = "Assets/Generated/Prefabs";
            Directory.CreateDirectory(prefabFolder);
            string prefabPath = $"{prefabFolder}/{assetName}.prefab";
            if (File.Exists(prefabPath))
                report.warnings.Add($"replaced existing prefab {prefabPath}");
            PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
            report.prefabPath = prefabPath;

            UnityEngine.Object.DestroyImmediate(instance);
        }
        catch
        {
            if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
            throw;
        }

        AssetDatabase.SaveAssets();
        report.ok = true;
        Debug.Log($"[ImportGeneratedAvatar] {report.prefabPath}  " +
                  $"hasHumanoid={report.hasHumanoidAvatar}  warnings={report.warnings.Count}");
        return report;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    static void CopyReplace(string source, string destination)
    {
        if (File.Exists(destination))
        {
            File.SetAttributes(destination, FileAttributes.Normal);
            File.Delete(destination);
        }
        File.Copy(source, destination, overwrite: false);
        File.SetAttributes(destination, FileAttributes.Normal);
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
        return args.TryGetValue(key, out var v) && !string.IsNullOrEmpty(v) ? v : fallback;
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
        Debug.Log("[ImportGeneratedAvatar] report " + json);
    }

    static string SanitizeName(string name)
    {
        foreach (char c in Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
        return name.Replace(' ', '_');
    }
}
