// Project-local job bridge used when the configured Unity project is already
// open in a licensed GUI Editor. Python writes a job into Library/GameFactory3A;
// this Editor script invokes the same public RunFromCLI method used by the
// batch transport, while command-line helpers read job/report paths from the
// bridge environment.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

[InitializeOnLoad]
public static class GameFactory3AEditorBridge
{
    [Serializable]
    private sealed class BridgeJob
    {
        public string request_id = "";
        public string class_method = "";
        public string job_path = "";
        public string report_path = "";
        public int retry_count;
    }

    [Serializable]
    private sealed class BridgeStatus
    {
        public bool ok;
        public string request_id = "";
        public string class_method = "";
        public string error = "";
    }

    private static readonly string Root = Path.Combine(
        Directory.GetParent(Application.dataPath).FullName,
        "Library",
        "GameFactory3A");
    private static readonly string Inbox = Path.Combine(Root, "inbox");
    private static readonly string Processing = Path.Combine(Root, "processing");
    private static readonly string Completed = Path.Combine(Root, "completed");
    private static bool executing;
    private const int MaxCompileRetries = 8;

    static GameFactory3AEditorBridge()
    {
        Directory.CreateDirectory(Inbox);
        Directory.CreateDirectory(Processing);
        Directory.CreateDirectory(Completed);
        EditorApplication.update += Poll;
    }

    public static string GetArgument(string name, string fallback = "")
    {
        string environmentName = "A3GAME_UNITY_BRIDGE_" +
            name.TrimStart('-').Replace('-', '_').ToUpperInvariant();
        string environmentValue = Environment.GetEnvironmentVariable(environmentName);
        if (!string.IsNullOrEmpty(environmentValue))
            return environmentValue;

        string[] args = Environment.GetCommandLineArgs();
        string flag = "--" + name.TrimStart('-');
        for (int index = 0; index < args.Length; index++)
        {
            if (!string.Equals(args[index], flag, StringComparison.OrdinalIgnoreCase))
                continue;
            if (index + 1 < args.Length && !args[index + 1].StartsWith("--"))
                return args[index + 1];
            return "";
        }
        return fallback;
    }

    private static void Poll()
    {
        if (executing || EditorApplication.isCompiling || EditorApplication.isUpdating)
            return;
        string path = Directory.GetFiles(Inbox, "*.json")
            .OrderBy(item => item, StringComparer.Ordinal)
            .FirstOrDefault();
        if (string.IsNullOrEmpty(path))
            return;
        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            if (EditorApplication.isPlaying)
                EditorApplication.isPlaying = false;
            return;
        }

        // Python may install a new Editor entry point immediately before
        // enqueueing the request. Unity can expose the bridge assembly for a
        // frame before AssetDatabase has imported and compiled that entry
        // point. Refresh and leave the job in the inbox so the next editor
        // tick retries after compilation instead of reporting a false method
        // failure and deleting the request.
        string requestedMethod = ReadRequestedMethod(path);
        if (!string.IsNullOrEmpty(requestedMethod) &&
            ResolveMethodOrNull(requestedMethod) == null)
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return;
        }

        executing = true;
        string processingPath = Path.Combine(Processing, Path.GetFileName(path));
        bool requeued = false;
        try
        {
            if (File.Exists(processingPath)) File.Delete(processingPath);
            File.Move(path, processingPath);
            var job = JsonUtility.FromJson<BridgeJob>(File.ReadAllText(processingPath));
            if (job == null || string.IsNullOrWhiteSpace(job.class_method))
                throw new InvalidDataException("Bridge job is missing class_method");

            Environment.SetEnvironmentVariable("A3GAME_UNITY_BRIDGE_JOB", job.job_path);
            Environment.SetEnvironmentVariable("A3GAME_UNITY_BRIDGE_REPORT", job.report_path);
            try
            {
                ResolveMethod(job.class_method).Invoke(null, null);
                if (ShouldRetryCompile(job))
                {
                    if (job.retry_count >= MaxCompileRetries)
                        throw new InvalidOperationException(
                            "Unity remained compiling after " + MaxCompileRetries + " retries");
                    job.retry_count++;
                    if (File.Exists(job.report_path)) File.Delete(job.report_path);
                    File.WriteAllText(path, JsonUtility.ToJson(job, true));
                    if (File.Exists(processingPath)) File.Delete(processingPath);
                    requeued = true;
                    return;
                }
            }
            finally
            {
                Environment.SetEnvironmentVariable("A3GAME_UNITY_BRIDGE_JOB", null);
                Environment.SetEnvironmentVariable("A3GAME_UNITY_BRIDGE_REPORT", null);
            }
            WriteStatus(job, true, "");
        }
        catch (Exception exception)
        {
            BridgeJob failedJob = null;
            try
            {
                failedJob = JsonUtility.FromJson<BridgeJob>(File.ReadAllText(processingPath));
            }
            catch { }
            Debug.LogError("[GameFactory3AEditorBridge] " + exception);
            WriteStatus(failedJob, false, exception.ToString());
        }
        finally
        {
            if (!requeued && File.Exists(processingPath)) File.Delete(processingPath);
            executing = false;
        }
    }

    private static bool ShouldRetryCompile(BridgeJob job)
    {
        if (job == null || string.IsNullOrWhiteSpace(job.report_path) ||
            !File.Exists(job.report_path)) return false;
        string report = File.ReadAllText(job.report_path);
        return report.IndexOf("\"name\": \"compile\"", StringComparison.OrdinalIgnoreCase) >= 0 &&
            (report.IndexOf("Unity is still compiling", StringComparison.OrdinalIgnoreCase) >= 0 ||
             report.IndexOf("Unity is still compiling or updating assets", StringComparison.OrdinalIgnoreCase) >= 0);
    }

    private static MethodInfo ResolveMethod(string classMethod)
    {
        int separator = classMethod.LastIndexOf('.');
        if (separator <= 0 || separator == classMethod.Length - 1)
            throw new ArgumentException("class_method must be Class.Method: " + classMethod);
        string typeName = classMethod.Substring(0, separator);
        string methodName = classMethod.Substring(separator + 1);
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            Type type = assembly.GetType(typeName, false);
            if (type == null) continue;
            MethodInfo method = type.GetMethod(
                methodName,
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static,
                null,
                Type.EmptyTypes,
                null);
            if (method != null) return method;
        }
        throw new MissingMethodException(typeName, methodName);
    }

    private static MethodInfo ResolveMethodOrNull(string classMethod)
    {
        try { return ResolveMethod(classMethod); }
        catch (MissingMethodException) { return null; }
    }

    private static string ReadRequestedMethod(string path)
    {
        try
        {
            var job = JsonUtility.FromJson<BridgeJob>(File.ReadAllText(path));
            return job != null ? job.class_method : "";
        }
        catch { return ""; }
    }

    private static void WriteStatus(BridgeJob job, bool ok, string error)
    {
        string requestId = job != null && !string.IsNullOrEmpty(job.request_id)
            ? job.request_id
            : "unknown";
        var status = new BridgeStatus
        {
            ok = ok,
            request_id = requestId,
            class_method = job != null ? job.class_method : "",
            error = error ?? "",
        };
        string target = Path.Combine(Completed, requestId + ".json");
        File.WriteAllText(target, JsonUtility.ToJson(status, true));
    }
}
