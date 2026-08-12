// engine_adapters/unity3d/import_generated/RunUnityTests.cs
//
// Runs the Unity Test Framework (EditMode or PlayMode) from the command line
// and writes a summary report with pass / fail / skip counts. The NUnit XML
// results are written to a temp file whose path is included in the report.
//
// Requires the Unity Test Framework package (com.unity.test-framework),
// which is included in every Unity project by default.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI (do NOT pass -quit; the editor must stay alive until tests finish):
//     Unity -batchmode -nographics -projectPath <proj> \
//           -executeMethod RunUnityTests.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to test_report.json>
//
// job.json keys: test_filter, test_platform
//
// test_filter  — comma-separated full test names to run (default: all).
// test_platform — "EditMode" (default) or "PlayMode".

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.TestTools.TestRunner.Api;
using UnityEngine;

public static class RunUnityTests
{
    [Serializable]
    public class TestReport
    {
        public bool ok;
        public string testResultsPath = "";
        public int total;
        public int passed;
        public int failed;
        public int skipped;
        public string error = "";
    }

    // ── Async state ───────────────────────────────────────────────────────────
    // TestRunnerApi.ExecuteTestsWithCallback is asynchronous: it returns
    // immediately and fires ICallbacks when the run finishes. We keep state in
    // static fields so the EditorApplication.update poll can detect completion,
    // write the report, and exit.

    static TestReport s_report;
    static string s_reportPath;
    static string s_resultsPath;
    static bool s_testsDone;
    static DateTime s_startTime;
    const double TimeoutSeconds = 1800; // 30 min — same as the Python launcher

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        s_report = new TestReport();
        s_reportPath = Get(args, "report", null);
        s_testsDone = false;
        s_startTime = DateTime.UtcNow;

        try
        {
            string testFilter = GetJobValue(args, "test_filter", null);
            string testPlatform = GetJobValue(args, "test_platform", "EditMode");

            // Temp file for the XML results summary.
            s_resultsPath = Path.Combine(Path.GetTempPath(),
                $"unity_test_results_{DateTime.Now:yyyyMMddHHmmss}.xml");

            // Build the filter. ExecutionSettings wraps a TestRunnerFilter
            // which supports assembly, name, and category filtering.
            var filter = new Filter();
            var testMode = string.Equals(testPlatform, "PlayMode",
                StringComparison.OrdinalIgnoreCase)
                ? TestMode.PlayMode
                : TestMode.EditMode;
            filter.testMode = testMode;

            if (!string.IsNullOrEmpty(testFilter))
            {
                filter.testNames = testFilter.Split(
                    new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            }

            if (testMode == TestMode.PlayMode && Application.isBatchMode)
            {
                Debug.LogWarning(
                    "[RunUnityTests] PlayMode tests in batchmode require the " +
                    "editor to enter play mode; this may not work headless. " +
                    "Prefer EditMode tests for CI.");
            }

            // Start the async run and register the completion callback.
            var api = ScriptableObject.CreateInstance<TestRunnerApi>();
            var executionSettings = new ExecutionSettings(filter);
            api.Execute(executionSettings);
            api.RegisterCallbacks(new TestCallbacks());

            // Register an update callback that polls for completion. In
            // batchmode without -quit, this keeps the editor alive until the
            // test run finishes (or times out).
            EditorApplication.update += OnTestsUpdate;
        }
        catch (Exception e)
        {
            s_report.ok = false;
            s_report.error = e.ToString();
            Debug.LogError("[RunUnityTests] " + e);
            WriteReport(s_report, s_reportPath);
            if (Application.isBatchMode)
                EditorApplication.Exit(1);
        }
    }

    // ── Update poll ───────────────────────────────────────────────────────────

    static void OnTestsUpdate()
    {
        if (!s_testsDone)
        {
            // Timeout: if the test run takes longer than expected, abort and
            // report an error so the caller is not left waiting forever.
            if ((DateTime.UtcNow - s_startTime).TotalSeconds > TimeoutSeconds)
            {
                s_report.ok = false;
                s_report.error = $"test run timed out after {TimeoutSeconds} seconds";
                s_testsDone = true;
            }
            return;
        }

        // Tests finished (or timed out) — write the report and exit.
        EditorApplication.update -= OnTestsUpdate;
        s_report.testResultsPath = s_resultsPath;
        WriteReport(s_report, s_reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(s_report.ok ? 0 : 1);
    }

    // ── Test runner callbacks ─────────────────────────────────────────────────

    class TestCallbacks : ICallbacks
    {
        public void RunStarted(ITestAdaptor testsToRun)
        {
            Debug.Log($"[RunUnityTests] run started: {testsToRun?.TestCaseCount ?? 0} tests");
        }

        public void RunFinished(ITestResultAdaptor result)
        {
            if (result == null)
            {
                s_report.ok = false;
                s_report.error = "test runner returned a null result";
                s_testsDone = true;
                return;
            }

            int passed = result.PassCount;
            int failed = result.FailCount;
            int inconclusive = result.InconclusiveCount;
            int skipped = result.SkipCount;
            int total = passed + failed + skipped + inconclusive;

            s_report.total = total;
            s_report.passed = passed;
            s_report.failed = failed;
            s_report.skipped = skipped + inconclusive;
            s_report.ok = failed == 0;
            s_report.testResultsPath = s_resultsPath;

            // Write a simple XML summary to the results path.
            try
            {
                var sb = new StringBuilder();
                sb.AppendLine("<?xml version=\"1.0\" encoding=\"utf-8\"?>");
                sb.AppendLine("<test-results>");
                sb.AppendLine($"  <total>{total}</total>");
                sb.AppendLine($"  <passed>{passed}</passed>");
                sb.AppendLine($"  <failed>{failed}</failed>");
                sb.AppendLine($"  <skipped>{skipped + inconclusive}</skipped>");
                sb.AppendLine($"  <inconclusive>{inconclusive}</inconclusive>");
                sb.AppendLine($"  <result-state>{result.ResultState}</result-state>");
                sb.AppendLine("</test-results>");
                File.WriteAllText(s_resultsPath, sb.ToString());
            }
            catch (Exception e)
            {
                Debug.LogWarning("[RunUnityTests] could not write results file: " + e.Message);
            }

            Debug.Log($"[RunUnityTests] run finished: total={total}  " +
                      $"passed={passed}  failed={failed}  skipped={s_report.skipped}");

            s_testsDone = true;
        }

        public void TestStarted(ITestAdaptor test)
        {
            // Per-test logging is intentionally silent — the summary is what
            // the caller needs. Enable for debugging if required.
        }

        public void TestFinished(ITestResultAdaptor result)
        {
            if (result != null && result.ResultState == "Failed")
            {
                Debug.LogWarning($"[RunUnityTests] FAILED: {result.Name} — {result.Message}");
            }
        }
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
        Debug.Log("[RunUnityTests] report " + json);
    }
}
