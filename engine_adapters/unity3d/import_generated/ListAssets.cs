// engine_adapters/unity3d/import_generated/ListAssets.cs
//
// Lists assets under a project folder, optionally filtered by type. Uses
// AssetDatabase.FindAssets so the query is instant — no scanning of the file
// system. The report includes path, name, type and class for every asset
// found.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod ListAssets.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to list_report.json>
//
// job.json keys: root, asset_type

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ListAssets
{
    [Serializable]
    public class AssetInfo
    {
        public string path = "";
        public string name = "";
        public string type = "";
        public string @class = "";
    }

    [Serializable]
    public class ListReport
    {
        public bool ok;
        public List<AssetInfo> assets = new List<AssetInfo>();
        public int count;
        public string error = "";
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new ListReport();
        string reportPath = Get(args, "report", null);

        try
        {
            string root = GetJobValue(args, "root", "Assets");
            string assetType = GetJobValue(args, "asset_type", null);
            report = List(root, assetType);
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[ListAssets] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── List ──────────────────────────────────────────────────────────────────

    /// <summary>
    /// Query AssetDatabase for assets under <paramref name="root"/>, optionally
    /// filtered by Unity type label (e.g. "Texture2D", "Material",
    /// "GameObject", "AnimationClip").
    /// </summary>
    /// <param name="root">Project-relative folder to search, e.g. "Assets/Generated".</param>
    /// <param name="assetType">Unity type name for the t: filter, or null/empty
    /// for all types.</param>
    public static ListReport List(string root = "Assets", string assetType = null)
    {
        var report = new ListReport();

        if (string.IsNullOrEmpty(root))
            root = "Assets";

        // Build the filter string. AssetDatabase.FindAssets supports "t:Type"
        // labels; an empty filter returns everything.
        string filter = string.IsNullOrEmpty(assetType) ? "" : $"t:{assetType}";
        string[] guids;
        if (string.IsNullOrEmpty(filter))
            guids = AssetDatabase.FindAssets("", new[] { root });
        else
            guids = AssetDatabase.FindAssets(filter, new[] { root });

        foreach (var guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);

            // FindAssets returns folders too; skip them unless the caller
            // explicitly asked for "DefaultAsset" (folders are DefaultAsset).
            if (AssetDatabase.IsValidFolder(path) &&
                !string.Equals(assetType, "DefaultAsset", StringComparison.OrdinalIgnoreCase))
                continue;

            var asset = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(path);
            var info = new AssetInfo
            {
                path = path,
                name = asset != null ? asset.name : Path.GetFileNameWithoutExtension(path),
                type = asset != null ? asset.GetType().FullName : "<unknown>",
                @class = asset != null ? asset.GetType().Name : "<unknown>"
            };
            report.assets.Add(info);
        }

        report.count = report.assets.Count;
        report.ok = true;
        Debug.Log($"[ListAssets] root={root}  type={assetType ?? "all"}  count={report.count}");
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
        Debug.Log("[ListAssets] report " + json);
    }
}
