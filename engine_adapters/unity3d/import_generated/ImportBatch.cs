// One Unity Editor invocation for a dependency-ordered asset import batch.
// The Python UnityClient writes a JSON job and this script performs all
// editor-side imports before the process exits, avoiding one license/import
// startup per asset.

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportBatch
{
    [Serializable]
    public class BatchEntry
    {
        public string asset_type = "";
        public string src = "";
        public string dest = "";
        public string name = "";
        public string skeleton_asset_path = "";
        public string package_root = "";
        public bool pre_extracted;
        public string world_id = "";
        public string project_id = "";
        public string publish = "false";
        public string replace_existing = "true";
        public string usage = "";
        public string category = "";
    }

    [Serializable]
    private class BatchJob
    {
        public BatchEntry[] entries;
    }

    [Serializable]
    public class BatchItemReport
    {
        public bool ok;
        public string asset_type = "";
        public string source = "";
        public string assetPath = "";
        public string prefabPath = "";
        public string runtimePrefabPath = "";
        public string animationClipPath = "";
        public string runtimeAnimationClipPath = "";
        public string scenePath = "";
        public string packageRoot = "";
        public int clipCount;
        public int importedAssetCount;
        public int extractedTextures;
        public int generatedMaterials;
        public int remappedMaterials;
        public int boundTextures;
        public List<string> importedPaths = new List<string>();
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    [Serializable]
    public class BatchReport
    {
        public bool ok;
        public int total;
        public int succeeded;
        public int failed;
        public List<BatchItemReport> items = new List<BatchItemReport>();
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        string reportPath = Get(args, "report", "");
        var report = new BatchReport();
        try
        {
            string jobPath = Get(args, "job", "");
            if (string.IsNullOrEmpty(jobPath) || !File.Exists(jobPath))
                throw new FileNotFoundException("Asset batch job was not found", jobPath);
            var job = JsonUtility.FromJson<BatchJob>(File.ReadAllText(jobPath));
            if (job == null || job.entries == null || job.entries.Length == 0)
                throw new InvalidDataException("Asset batch job contains no entries");

            report = ImportEntries(job.entries);
        }
        catch (Exception exception)
        {
            report.ok = false;
            report.error = exception.ToString();
            Debug.LogError("[ImportBatch] " + exception);
        }
        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    public static BatchReport ImportEntries(BatchEntry[] entries)
    {
        var report = new BatchReport();
        if (entries == null || entries.Length == 0)
            throw new InvalidDataException("Asset batch contains no entries");
        report.total = entries.Length;
        foreach (var entry in entries)
        {
            var item = ImportOne(entry);
            report.items.Add(item);
            if (item.ok) report.succeeded++; else report.failed++;
        }
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        report.ok = report.failed == 0;
        return report;
    }

    public static BatchItemReport ImportOne(BatchEntry entry)
    {
        var item = new BatchItemReport
        {
            asset_type = entry.asset_type ?? "",
            source = entry.src ?? "",
        };
        try
        {
            string type = (entry.asset_type ?? "").Trim().ToLowerInvariant();
            if (type == "avatar")
            {
                var result = ImportGeneratedAvatar.Import(entry.src, entry.dest, entry.name);
                item.ok = result.ok;
                item.assetPath = result.assetPath;
                item.prefabPath = result.prefabPath;
                item.runtimePrefabPath = result.runtimePrefabPath;
                item.extractedTextures = result.extractedTextures;
                item.generatedMaterials = result.generatedMaterials;
                item.remappedMaterials = result.remappedMaterials;
                item.boundTextures = result.boundTextures;
                item.warnings.AddRange(result.warnings);
            }
            else if (type == "motion")
            {
                var result = ImportGeneratedMotion.Import(
                    entry.src, entry.dest, entry.name, entry.skeleton_asset_path);
                item.ok = result.ok;
                item.assetPath = result.assetPath;
                item.animationClipPath = result.animationClipPath;
                item.runtimeAnimationClipPath = result.runtimeAnimationClipPath;
                item.clipCount = result.clipCount;
                item.warnings.AddRange(result.warnings);
            }
            else if (type == "scene" || type == "environment")
            {
                var result = ImportUnityPackage.Import(
                    entry.src,
                    string.IsNullOrEmpty(entry.package_root)
                        ? "Assets/Ilumisoft/Nora Prime" : entry.package_root,
                    entry.pre_extracted);
                item.ok = result.ok;
                item.assetPath = result.assetPath;
                item.scenePath = result.assetPath;
                item.packageRoot = result.packageRoot;
                item.importedAssetCount = result.importedAssetCount;
                item.warnings.AddRange(result.warnings);
            }
            else
            {
                var result = ImportGeneratedMesh.Import(
                    entry.src,
                    entry.dest,
                    entry.name,
                    ParseUsage(entry.usage),
                    null,
                    null,
                    false,
                    "Assets/Generated/Prefabs");
                item.ok = result.ok;
                item.assetPath = result.assetPath;
                item.prefabPath = result.prefabPath;
                item.extractedTextures = result.extractedTextures;
                item.generatedMaterials = result.generatedMaterials;
                item.remappedMaterials = result.remappedMaterials;
                item.boundTextures = result.boundTextures;
                item.warnings.AddRange(result.warnings);
            }
        }
        catch (Exception exception)
        {
            item.ok = false;
            item.error = exception.ToString();
        }
        AddPath(item.importedPaths, item.assetPath);
        AddPath(item.importedPaths, item.prefabPath);
        AddPath(item.importedPaths, item.runtimePrefabPath);
        AddPath(item.importedPaths, item.animationClipPath);
        AddPath(item.importedPaths, item.runtimeAnimationClipPath);
        AddPath(item.importedPaths, item.scenePath);
        return item;
    }

    private static ImportGeneratedMesh.Usage ParseUsage(string value)
    {
        ImportGeneratedMesh.Usage usage;
        return Enum.TryParse(value, true, out usage)
            ? usage : ImportGeneratedMesh.Usage.Asset;
    }

    private static void AddPath(List<string> paths, string path)
    {
        if (!string.IsNullOrEmpty(path) && !paths.Contains(path)) paths.Add(path);
    }

    private static Dictionary<string, string> ParseArgs(string[] argv)
    {
        var result = new Dictionary<string, string>();
        for (int index = 0; index < argv.Length; index++)
        {
            if (!argv[index].StartsWith("--")) continue;
            string key = argv[index].Substring(2);
            string value = index + 1 < argv.Length && !argv[index + 1].StartsWith("--")
                ? argv[++index] : "";
            result[key] = value;
        }
        return result;
    }

    private static string Get(Dictionary<string, string> args, string key, string fallback)
    {
        if (args.TryGetValue(key, out string value) && !string.IsNullOrEmpty(value))
            return value;
        return A3GameForgeEditorBridge.GetArgument(key, fallback);
    }

    private static void WriteReport(object value, string path)
    {
        string json = JsonUtility.ToJson(value, true);
        if (!string.IsNullOrEmpty(path))
        {
            string parent = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.WriteAllText(path, json);
        }
        Debug.Log("[ImportBatch] report " + json);
    }
}
