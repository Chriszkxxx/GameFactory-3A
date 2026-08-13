// engine_adapters/unity3d/import_generated/ImportGeneratedMotion.cs
//
// Imports an animation clip (FBX / GLB with baked animation) and configures
// ModelImporter for Humanoid animation, then extracts the AnimationClip(s)
// into standalone .anim assets for direct reference.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod ImportGeneratedMotion.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to motion_report.json>
//
// job.json keys: src, dest, name, skeleton_asset_path

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportGeneratedMotion
{
    [Serializable]
    public class MotionReport
    {
        public bool ok;
        public string assetPath = "";
        public string animationClipPath = "";
        public string runtimeAnimationClipPath = "";
        public int clipCount;
        public int defaultClipCount;
        public string sourceAvatarPath = "";
        public List<string> importedSubAssets = new List<string>();
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new MotionReport();
        string reportPath = Get(args, "report", null);

        try
        {
            string src = GetJobValue(args, "src", null);
            if (string.IsNullOrEmpty(src))
                throw new ArgumentException("job 'src' (path to animation .fbx/.glb) is required");

            report = Import(
                src,
                GetJobValue(args, "dest", "Assets/Generated/Motions"),
                GetJobValue(args, "name", null),
                GetJobValue(args, "skeleton_asset_path", null)
            );
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[ImportGeneratedMotion] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Import ────────────────────────────────────────────────────────────────

    /// <summary>
    /// Copy an animation source into the project, configure ModelImporter for
    /// Humanoid animation, and extract the first clip as a standalone .anim.
    /// </summary>
    /// <param name="srcPath">Absolute path to the generated animation file.</param>
    /// <param name="destFolder">Project-relative folder for the model asset.</param>
    /// <param name="assetName">Asset base name; defaults to the source file name.</param>
    /// <param name="skeletonAssetPath">Optional path to a source Avatar for rig
    /// copy (retargeting the clip against an existing skeleton).</param>
    public static MotionReport Import(
        string srcPath,
        string destFolder = "Assets/Generated/Motions",
        string assetName = null,
        string skeletonAssetPath = null)
    {
        var report = new MotionReport();

        if (!File.Exists(srcPath))
            throw new FileNotFoundException("animation source not found", srcPath);

        string ext = Path.GetExtension(srcPath).ToLowerInvariant();
        if (ext != ".fbx" && ext != ".glb" && ext != ".gltf")
            report.warnings.Add($"unusual extension {ext}; animation import expects .fbx/.glb");

        if (string.IsNullOrEmpty(assetName))
            assetName = SanitizeName(Path.GetFileNameWithoutExtension(srcPath));

        // 1. Copy into the project.
        Directory.CreateDirectory(destFolder);
        string assetPath = $"{destFolder}/{assetName}{ext}";
        CopyReplace(srcPath, assetPath);
        AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
        AssetDatabase.Refresh();
        report.assetPath = assetPath;

        // 2. Configure animation import via ModelImporter.
        var importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
        if (importer == null)
            throw new InvalidOperationException($"no ModelImporter for {assetPath}");

        importer.animationType = ModelImporterAnimationType.Human;
        importer.importAnimation = true;

        // If a source avatar is provided, copy its rig so the clip retargets
        // against the same skeleton instead of creating a new one.
        if (!string.IsNullOrEmpty(skeletonAssetPath))
        {
            var sourceAvatar = ResolveAvatar(skeletonAssetPath, out string sourceAvatarPath);
            if (sourceAvatar != null)
            {
                importer.sourceAvatar = sourceAvatar;
                report.sourceAvatarPath = sourceAvatarPath;
            }
            else
            {
                report.warnings.Add(
                    $"skeleton_asset_path '{skeletonAssetPath}' loaded no Avatar; " +
                    "using default Humanoid rig");
            }
        }

        // Unity may expose FBX takes only through defaultClipAnimations. Copy
        // those defaults into clipAnimations before reimport so the takes are
        // materialized as AnimationClip sub-assets.
        ModelImporterClipAnimation[] defaultClips = importer.defaultClipAnimations;
        report.defaultClipCount = defaultClips != null ? defaultClips.Length : 0;
        if ((importer.clipAnimations == null || importer.clipAnimations.Length == 0) &&
            defaultClips != null && defaultClips.Length > 0)
        {
            bool loop = IsLoopingMotion(assetName);
            for (int index = 0; index < defaultClips.Length; index++)
            {
                if (index == 0) defaultClips[index].name = assetName;
                defaultClips[index].loopTime = loop;
            }
            importer.clipAnimations = defaultClips;
        }

        importer.SaveAndReimport();
        AssetDatabase.Refresh();

        // 3. Collect AnimationClip sub-assets produced by the import.
        var subAssets = AssetDatabase.LoadAllAssetRepresentationsAtPath(assetPath);
        AnimationClip firstClip = null;
        int clipCount = 0;
        foreach (var sub in subAssets)
        {
            if (sub != null)
                report.importedSubAssets.Add(sub.GetType().Name + ":" + sub.name);
            if (sub is AnimationClip clip)
            {
                clipCount++;
                if (firstClip == null) firstClip = clip;
            }
        }

        report.clipCount = clipCount;

        if (firstClip == null)
        {
            throw new InvalidOperationException(
                "Unity imported no AnimationClip from " + assetPath +
                "; defaultClipAnimations=" + report.defaultClipCount);
        }
        else
        {
            // 4. Save the first clip as a standalone .anim asset so it can be
            //    referenced directly by Animators and Timelines.
            string clipFolder = "Assets/Generated/Animations";
            Directory.CreateDirectory(clipFolder);
            string clipPath = $"{clipFolder}/{assetName}.anim";

            AnimationClip outputClip;
            var existing = AssetDatabase.LoadAssetAtPath<AnimationClip>(clipPath);
            if (existing != null)
            {
                EditorUtility.CopySerialized(firstClip, existing);
                outputClip = existing;
                report.warnings.Add($"overwrote existing animation clip {clipPath}");
            }
            else
            {
                var standalone = new AnimationClip { name = assetName };
                EditorUtility.CopySerialized(firstClip, standalone);
                AssetDatabase.CreateAsset(standalone, clipPath);
                outputClip = standalone;
            }
            AnimationClipSettings settings = AnimationUtility.GetAnimationClipSettings(outputClip);
            settings.loopTime = IsLoopingMotion(assetName);
            AnimationUtility.SetAnimationClipSettings(outputClip, settings);
            EditorUtility.SetDirty(outputClip);
            report.animationClipPath = clipPath;
            string runtimeFolder = "Assets/Resources/A3Game/Animations";
            Directory.CreateDirectory(runtimeFolder);
            string runtimePath = $"{runtimeFolder}/{assetName}.anim";
            var runtimeExisting = AssetDatabase.LoadAssetAtPath<AnimationClip>(runtimePath);
            if (runtimeExisting != null)
            {
                EditorUtility.CopySerialized(outputClip, runtimeExisting);
                EditorUtility.SetDirty(runtimeExisting);
            }
            else
            {
                var runtimeClip = new AnimationClip { name = assetName };
                EditorUtility.CopySerialized(outputClip, runtimeClip);
                AssetDatabase.CreateAsset(runtimeClip, runtimePath);
            }
            report.runtimeAnimationClipPath = runtimePath;
        }

        AssetDatabase.SaveAssets();
        report.ok = true;
        Debug.Log($"[ImportGeneratedMotion] {report.assetPath}  clips={report.clipCount}  " +
                  $"warnings={report.warnings.Count}");
        return report;
    }

    static Avatar ResolveAvatar(string skeletonAssetPath, out string resolvedPath)
    {
        resolvedPath = "";
        Avatar direct = AssetDatabase.LoadAssetAtPath<Avatar>(skeletonAssetPath);
        if (direct != null)
        {
            resolvedPath = skeletonAssetPath;
            return direct;
        }

        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(skeletonAssetPath);
        if (prefab != null)
        {
            Animator animator = prefab.GetComponentInChildren<Animator>(true);
            if (animator != null && animator.avatar != null)
            {
                resolvedPath = AssetDatabase.GetAssetPath(animator.avatar);
                return animator.avatar;
            }
        }

        foreach (string dependency in AssetDatabase.GetDependencies(skeletonAssetPath, true))
        {
            foreach (UnityEngine.Object asset in AssetDatabase.LoadAllAssetsAtPath(dependency))
            {
                if (asset is Avatar avatar)
                {
                    resolvedPath = dependency;
                    return avatar;
                }
            }
        }
        return null;
    }

    static bool IsLoopingMotion(string assetName)
    {
        string normalized = (assetName ?? "").ToLowerInvariant();
        return normalized.Contains("idle") ||
               normalized.Contains("jog") ||
               normalized.Contains("walk") ||
               normalized.Contains("run");
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
        Debug.Log("[ImportGeneratedMotion] report " + json);
    }

    static string SanitizeName(string name)
    {
        foreach (char c in Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
        return name.Replace(' ', '_');
    }
}
