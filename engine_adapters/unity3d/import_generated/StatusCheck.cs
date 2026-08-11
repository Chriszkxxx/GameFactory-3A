// engine_adapters/unity3d/import_generated/StatusCheck.cs
//
// Health probe: reports the Unity version, project path, editor mode and a
// timestamp. No job keys are required — the script exists to confirm that the
// editor is reachable, batchmode works and the report file can be written.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod StatusCheck.RunFromCLI \
//           --report <abs path to status_report.json>
//
// (A --job file is accepted but not required; all values have sensible defaults.)

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class StatusCheck
{
    [Serializable]
    public class StatusReport
    {
        public bool ok;
        public string unityVersion = "";
        public string projectPath = "";
        public string editorMode = "";
        public string timestamp = "";
        public string error = "";
    }

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new StatusReport();
        string reportPath = Get(args, "report", null);

        try
        {
            report = Check();
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[StatusCheck] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Check ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// Gather basic editor / project information. Always succeeds unless the
    /// editor is in a broken state; the caller uses the presence of the report
    /// file and the <c>ok</c> flag to confirm the editor is reachable.
    /// </summary>
    public static StatusReport Check()
    {
        var report = new StatusReport
        {
            unityVersion = Application.unityVersion,
            projectPath = Application.dataPath,
            editorMode = Application.isBatchMode ? "batchmode" : "interactive",
            timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
            ok = true
        };

        Debug.Log($"[StatusCheck] Unity {report.unityVersion}  " +
                  $"{report.editorMode}  project={report.projectPath}");
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
        Debug.Log("[StatusCheck] report " + json);
    }
}
