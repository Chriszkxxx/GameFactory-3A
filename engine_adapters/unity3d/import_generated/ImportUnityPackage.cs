using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportUnityPackage
{
    [Serializable]
    private class PackageReport
    {
        public bool ok;
        public string source = "";
        public string assetPath = "";
        public string packageRoot = "";
        public int importedAssetCount;
        public bool preExtracted;
        public List<string> warnings = new List<string>();
        public string error = "";
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
            if (!File.Exists(source) || Path.GetExtension(source).ToLowerInvariant() != ".unitypackage")
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
            report.assetPath = AssetDatabase.LoadAssetAtPath<SceneAsset>(
                packageRoot + "/Scenes/Demo.unity") != null
                ? packageRoot + "/Scenes/Demo.unity"
                : packageRoot;
            report.importedAssetCount = Directory.GetFiles(
                absoluteRoot,
                "*",
                SearchOption.AllDirectories).Length;
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
        return args.TryGetValue(key, out string value) && !string.IsNullOrEmpty(value)
            ? value
            : fallback;
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
