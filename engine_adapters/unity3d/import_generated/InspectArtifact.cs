// engine_adapters/unity3d/import_generated/InspectArtifact.cs
//
// Loads a Unity asset by path and inspects it via System.Reflection: lists the
// components on a GameObject/prefab and enumerates the public properties and
// fields of each. Used by the pipeline to verify that an imported asset has
// the expected shape without opening the editor.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod InspectArtifact.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to inspect_report.json>
//
// job.json keys: asset_path

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEngine;

public static class InspectArtifact
{
    [Serializable]
    public class InspectReport
    {
        public bool ok;
        public string assetPath = "";
        public string name = "";
        public string type = "";
        public List<string> components = new List<string>();
        public List<string> properties = new List<string>();
        public string error = "";
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new InspectReport();
        string reportPath = Get(args, "report", null);

        try
        {
            string assetPath = GetJobValue(args, "asset_path", null);
            if (string.IsNullOrEmpty(assetPath))
                throw new ArgumentException("job 'asset_path' is required");

            report = Inspect(assetPath);
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[InspectArtifact] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Inspect ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Load an asset at the given project-relative path and inspect it with
    /// System.Reflection. For GameObjects / prefabs, every component is listed
    /// and its public properties and fields are enumerated.
    /// </summary>
    /// <param name="assetPath">Project-relative asset path, e.g.
    /// "Assets/Generated/Prefabs/Sword_001.prefab".</param>
    public static InspectReport Inspect(string assetPath)
    {
        var report = new InspectReport { assetPath = assetPath };

        var asset = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(assetPath);
        if (asset == null)
            throw new InvalidOperationException(
                $"no asset found at '{assetPath}'; check the path and that the " +
                "asset has been imported");

        report.name = asset.name;
        report.type = asset.GetType().FullName;

        if (asset is GameObject go)
        {
            // List every component on the GameObject (and its children for
            // prefabs, which is what you usually want to verify).
            var comps = go.GetComponentsInChildren<Component>(true);
            foreach (var c in comps)
            {
                if (c == null)
                {
                    report.components.Add("<missing script reference>");
                    continue;
                }
                string compType = c.GetType().FullName;
                string goPath = GetTransformPath(c.transform);
                report.components.Add(string.IsNullOrEmpty(goPath)
                    ? compType
                    : $"{goPath} → {compType}");
            }

            // Inspect properties of each component via reflection.
            foreach (var c in comps)
            {
                if (c == null) continue;
                InspectObjectProperties(c, report);
            }
        }
        else
        {
            // Non-GameObject asset (Material, Texture, AnimationClip, etc.) —
            // inspect its public properties and fields directly.
            InspectObjectProperties(asset, report);
        }

        report.ok = true;
        Debug.Log($"[InspectArtifact] {assetPath}  type={report.type}  " +
                  $"components={report.components.Count}  properties={report.properties.Count}");
        return report;
    }

    /// <summary>
    /// Enumerate the public instance properties and fields of an object and
    /// add "TypeName.Member = value" entries to the report. Indexers and
    /// properties that throw on read are skipped with an error annotation.
    /// </summary>
    static void InspectObjectProperties(UnityEngine.Object obj, InspectReport report)
    {
        var type = obj.GetType();

        // Public properties (instance, non-indexer).
        var props = type.GetProperties(
            BindingFlags.Public | BindingFlags.Instance);
        foreach (var p in props)
        {
            if (p.GetIndexParameters().Length > 0) continue; // skip indexers
            try
            {
                object val = p.GetValue(obj, null);
                report.properties.Add(
                    $"{type.Name}.{p.Name} = {FormatValue(val)}");
            }
            catch (Exception ex)
            {
                report.properties.Add(
                    $"{type.Name}.{p.Name} = <error: {ex.Message}>");
            }
        }

        // Public fields (instance).
        var fields = type.GetFields(
            BindingFlags.Public | BindingFlags.Instance);
        foreach (var f in fields)
        {
            try
            {
                object val = f.GetValue(obj);
                report.properties.Add(
                    $"{type.Name}.{f.Name} = {FormatValue(val)}");
            }
            catch (Exception ex)
            {
                report.properties.Add(
                    $"{type.Name}.{f.Name} = <error: {ex.Message}>");
            }
        }
    }

    static string FormatValue(object val)
    {
        if (val == null) return "null";
        if (val is UnityEngine.Object uo && uo == null) return "null (destroyed)";
        var str = val.ToString();
        // Truncate long values so a single property doesn't dominate the report.
        if (str != null && str.Length > 200)
            return str.Substring(0, 200) + "…";
        return str;
    }

    /// <summary>
    /// Build a slash-delimited path from the scene root to this transform,
    /// e.g. "World/Tree_000/Mesh". Returns the GameObject name if the transform
    /// has no parent.
    /// </summary>
    static string GetTransformPath(Transform t)
    {
        if (t == null) return "";
        var parts = new List<string>();
        while (t != null)
        {
            parts.Insert(0, t.name);
            t = t.parent;
        }
        return string.Join("/", parts);
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
        Debug.Log("[InspectArtifact] report " + json);
    }
}
