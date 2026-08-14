using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportUnityPackage
{
    [Serializable]
    public class PackageReport
    {
        public bool ok;
        public string source = "";
        public string assetPath = "";
        public string packageRoot = "";
        public int importedAssetCount;
        public int sceneObjectCount;
        public int prefabColliderCount;
        public int shaderGraphCount;
        public int brokenShaderCount;
        public bool preExtracted;
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    public static PackageReport Import(
        string source,
        string packageRoot = "Assets/Ilumisoft/Nora Prime",
        bool preExtracted = false)
    {
        var report = new PackageReport();
        if (!File.Exists(source) ||
            Path.GetExtension(source).ToLowerInvariant() != ".unitypackage")
            throw new FileNotFoundException("Unity package was not found", source);

        if (!preExtracted)
            AssetDatabase.ImportPackage(source, false);
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        AssetDatabase.SaveAssets();

        string absoluteRoot = Path.GetFullPath(packageRoot);
        if (!Directory.Exists(absoluteRoot))
            throw new DirectoryNotFoundException(
                "Expected imported package root was not found: " + packageRoot);
        report.ok = true;
        report.source = source;
        report.packageRoot = packageRoot;
        report.preExtracted = preExtracted;
        report.assetPath = FindScenePath(packageRoot);
        if (string.IsNullOrEmpty(report.assetPath))
            report.warnings.Add("package contains no Unity scene asset");
        report.importedAssetCount = Directory.GetFiles(
            absoluteRoot, "*", SearchOption.AllDirectories).Length;
        report.sceneObjectCount = CountSceneObjects(report.assetPath);
        report.prefabColliderCount = CountPrefabColliders(absoluteRoot);
        report.shaderGraphCount = Directory.GetFiles(
            absoluteRoot, "*.shadergraph", SearchOption.AllDirectories).Length;
        report.brokenShaderCount = CountBrokenShaders(absoluteRoot);
        if (report.sceneObjectCount == 0)
            report.warnings.Add("Imported package scene contains no serialized GameObjects");
        if (report.prefabColliderCount == 0)
            report.warnings.Add(
                "Imported package contains no prefab colliders; scene composition must bake " +
                "structural colliders before building a Player");
        if (report.brokenShaderCount > 0)
            report.warnings.Add("Imported package contains shader/material references that Unity could not resolve");
        return report;
    }

    private static int CountSceneObjects(string scenePath)
    {
        if (string.IsNullOrEmpty(scenePath)) return 0;
        string absolute = Path.GetFullPath(scenePath);
        if (!File.Exists(absolute)) return 0;
        string text = File.ReadAllText(absolute);
        int count = 0;
        int index = 0;
        while ((index = text.IndexOf("--- !u!1 ", index, StringComparison.Ordinal)) >= 0)
        {
            count++;
            index += 8;
        }
        return count;
    }

    private static int CountPrefabColliders(string root)
    {
        int count = 0;
        foreach (string file in Directory.GetFiles(root, "*.prefab", SearchOption.AllDirectories))
        {
            string text = File.ReadAllText(file);
            count += CountToken(text, "MeshCollider:") + CountToken(text, "BoxCollider:") +
                CountToken(text, "CapsuleCollider:") + CountToken(text, "CharacterController:");
        }
        return count;
    }

    private static int CountBrokenShaders(string root)
    {
        int count = 0;
        foreach (string file in Directory.GetFiles(root, "*.mat", SearchOption.AllDirectories))
            if (File.ReadAllText(file).Contains("Hidden/InternalErrorShader")) count++;
        return count;
    }

    private static int CountToken(string text, string token)
    {
        int count = 0;
        int index = 0;
        while ((index = text.IndexOf(token, index, StringComparison.Ordinal)) >= 0)
        {
            count++;
            index += token.Length;
        }
        return count;
    }

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        string reportPath = Get(args, "report", "");
        var report = new PackageReport();
        try
        {
            string jobPath = Get(args, "job", "");
            string json = File.ReadAllText(jobPath);
            string source = JsonString(json, "src", "");
            string packageRoot = JsonString(
                json,
                "package_root",
                "Assets/Ilumisoft/Nora Prime");
            bool preExtracted = JsonBool(json, "pre_extracted", false);
            report = Import(source, packageRoot, preExtracted);
        }
        catch (Exception exception)
        {
            report.ok = false;
            report.error = exception.ToString();
            Debug.LogError("[ImportUnityPackage] " + exception);
        }
        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    private static string JsonString(string json, string key, string fallback)
    {
        string marker = "\"" + key + "\"";
        int keyIndex = json.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (keyIndex < 0) return fallback;
        int colon = json.IndexOf(':', keyIndex + marker.Length);
        int start = colon >= 0 ? json.IndexOf('"', colon + 1) : -1;
        int end = start >= 0 ? json.IndexOf('"', start + 1) : -1;
        return start >= 0 && end > start
            ? json.Substring(start + 1, end - start - 1).Replace("\\/", "/")
            : fallback;
    }

    private static bool JsonBool(string json, string key, bool fallback)
    {
        string marker = "\"" + key + "\"";
        int keyIndex = json.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (keyIndex < 0) return fallback;
        int colon = json.IndexOf(':', keyIndex + marker.Length);
        if (colon < 0) return fallback;
        string value = json.Substring(colon + 1).TrimStart();
        if (value.StartsWith("true", StringComparison.OrdinalIgnoreCase)) return true;
        if (value.StartsWith("false", StringComparison.OrdinalIgnoreCase)) return false;
        return fallback;
    }

    private static string FindScenePath(string packageRoot)
    {
        string[] guids = AssetDatabase.FindAssets("t:Scene", new[] { packageRoot });
        string selected = "";
        long selectedSize = -1;
        int selectedScore = -1;
        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            if (string.IsNullOrEmpty(path)) continue;
            string name = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
            int score = name == "main" ? 100 : name == "demo" ? 50 : 0;
            long size = File.Exists(path) ? new FileInfo(path).Length : 0;
            if (score > selectedScore || (score == selectedScore && size > selectedSize))
            {
                selected = path;
                selectedScore = score;
                selectedSize = size;
            }
        }
        return selected;
    }

    private static Dictionary<string, string> ParseArgs(string[] argv)
    {
        var result = new Dictionary<string, string>();
        for (int index = 0; index < argv.Length; index++)
        {
            if (!argv[index].StartsWith("--")) continue;
            string key = argv[index].Substring(2);
            string value = index + 1 < argv.Length && !argv[index + 1].StartsWith("--")
                ? argv[++index]
                : "";
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
        Debug.Log("[ImportUnityPackage] report " + json);
    }
}
