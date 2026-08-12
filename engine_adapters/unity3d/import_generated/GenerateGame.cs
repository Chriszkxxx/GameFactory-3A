// Unity-native generated game job.
// Python writes one manifest, then the already-open (or one newly launched)
// Editor owns the complete import/compile/build/play lifecycle.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class GenerateGame
{
    [Serializable]
    public class PluginEntry
    {
        public string source_root = "";
        public string target = "";
        public string test_source = "";
        public bool replace_existing = true;
    }

    [Serializable]
    public class GenerateJob
    {
        public ImportBatch.BatchEntry[] assets;
        public PluginEntry[] plugins;
        public string scene_job = "";
        public string build_job = "";
        public string play_scene = "";
        public bool enter_play;
    }

    [Serializable]
    public class StageReport
    {
        public string name = "";
        public bool ok;
        public string error = "";
        public List<string> artifacts = new List<string>();
    }

    [Serializable]
    public class GenerateReport
    {
        public bool ok;
        public string project_path = "";
        public List<StageReport> stages = new List<StageReport>();
        public List<string> warnings = new List<string>();
        public List<string> errors = new List<string>();
        public string error = "";
    }

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        string reportPath = Get(args, "report", "");
        GenerateReport report;
        try
        {
            string jobPath = Get(args, "job", "");
            report = RunJobFile(jobPath);
        }
        catch (Exception exception)
        {
            report = new GenerateReport
            {
                ok = false,
                error = exception.ToString(),
            };
            report.errors.Add(report.error);
            Debug.LogError("[GenerateGame] " + exception);
        }
        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    public static GenerateReport RunJobFile(string jobPath)
    {
        if (string.IsNullOrEmpty(jobPath) || !File.Exists(jobPath))
            throw new FileNotFoundException("Generated game job was not found", jobPath);
        string raw = File.ReadAllText(jobPath);
        // UnityEditorTransport wraps the requested method arguments in a
        // temporary job file. Resolve the nested project-local manifest when
        // running through that transport.
        string nestedPath = JsonString(raw, "manifest", "");
        if (string.IsNullOrEmpty(nestedPath))
            nestedPath = JsonString(raw, "job", "");
        if (!string.IsNullOrEmpty(nestedPath) && File.Exists(nestedPath))
        {
            jobPath = nestedPath;
            raw = File.ReadAllText(jobPath);
        }
        var job = JsonUtility.FromJson<GenerateJob>(raw);
        if (job == null)
            throw new InvalidDataException("Generated game job JSON is invalid");

        var report = new GenerateReport
        {
            project_path = Directory.GetParent(Application.dataPath).FullName,
        };

        var plugins = RunPlugins(job.plugins, report);
        report.stages.Add(plugins);
        if (!plugins.ok) return Finish(report);

        var assets = RunAssets(job.assets, report);
        report.stages.Add(assets);
        if (!assets.ok) return Finish(report);

        if (!string.IsNullOrWhiteSpace(job.scene_job))
        {
            var stage = new StageReport { name = "compose_scene" };
            try
            {
                var scene = ComposeScene.ComposeJobFile(job.scene_job);
                stage.ok = scene.ok;
                if (!string.IsNullOrEmpty(scene.scenePath)) stage.artifacts.Add(scene.scenePath);
                report.warnings.AddRange(scene.warnings ?? new List<string>());
                if (!scene.ok) stage.error = scene.error;
            }
            catch (Exception exception)
            {
                stage.ok = false;
                stage.error = exception.ToString();
            }
            report.stages.Add(stage);
            if (!stage.ok) return Finish(report);
        }

        // Refresh synchronously before handing control to BuildPipeline. Unity
        // owns script import/compilation; no external compiler is involved.
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        var compile = WaitForCompilation();
        report.stages.Add(compile);
        if (!compile.ok) return Finish(report);

        if (!string.IsNullOrWhiteSpace(job.build_job))
        {
            var stage = RunBuild(job.build_job, report);
            report.stages.Add(stage);
            if (!stage.ok) return Finish(report);
        }

        if (job.enter_play)
        {
            var stage = new StageReport { name = "play_mode" };
            try
            {
                if (!string.IsNullOrWhiteSpace(job.play_scene))
                    EditorSceneManager.OpenScene(job.play_scene, OpenSceneMode.Single);
                EditorApplication.isPlaying = true;
                stage.ok = true;
                if (!string.IsNullOrWhiteSpace(job.play_scene)) stage.artifacts.Add(job.play_scene);
            }
            catch (Exception exception)
            {
                stage.ok = false;
                stage.error = exception.ToString();
            }
            report.stages.Add(stage);
            if (!stage.ok) return Finish(report);
        }
        return Finish(report);
    }

    private static StageReport RunPlugins(PluginEntry[] entries, GenerateReport report)
    {
        var stage = new StageReport { name = "install_plugins" };
        try
        {
            foreach (var entry in entries ?? new PluginEntry[0])
            {
                if (entry == null || string.IsNullOrWhiteSpace(entry.source_root)) continue;
                if (!Directory.Exists(entry.source_root))
                    throw new DirectoryNotFoundException(entry.source_root);
                // Older plugin.install runs placed generated tests beside the
                // plugin (for example Assets/FPSArenaGameplay.Tests), while
                // the one-job contract keeps them under target/Tests. Remove
                // that legacy sibling when replacing a generated plugin so
                // Unity never sees two asmdefs with the same assembly name.
                if (entry.replace_existing && !string.IsNullOrWhiteSpace(entry.test_source))
                {
                    string legacyTests = entry.target + ".Tests";
                    if (Directory.Exists(legacyTests))
                        Directory.Delete(legacyTests, true);
                }
                CopyTree(entry.source_root, entry.target);
                if (!string.IsNullOrWhiteSpace(entry.test_source) && Directory.Exists(entry.test_source))
                    CopyTree(entry.test_source, Path.Combine(entry.target, "Tests"));
                stage.artifacts.Add(entry.target);
            }
            stage.ok = true;
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        }
        catch (Exception exception)
        {
            stage.ok = false;
            stage.error = exception.ToString();
        }
        return stage;
    }

    private static StageReport RunAssets(ImportBatch.BatchEntry[] entries, GenerateReport report)
    {
        var stage = new StageReport { name = "import_assets" };
        try
        {
            if (entries == null || entries.Length == 0)
            {
                stage.ok = true;
                return stage;
            }
            var result = ImportBatch.ImportEntries(entries);
            stage.ok = result.ok;
            foreach (var item in result.items)
                stage.artifacts.AddRange(item.importedPaths ?? new List<string>());
            report.warnings.AddRange(result.warnings ?? new List<string>());
            if (!result.ok) stage.error = result.error;
        }
        catch (Exception exception)
        {
            stage.ok = false;
            stage.error = exception.ToString();
        }
        return stage;
    }

    private static StageReport WaitForCompilation()
    {
        var stage = new StageReport { name = "compile" };
        // ForceSynchronousImport normally leaves no pending compilation in a
        // CLI job. In the interactive bridge, report the actual state instead
        // of pretending an asynchronous compile completed.
        // ForceSynchronousImport can leave the asset pipeline's updating flag
        // set until the next editor tick even after script compilation has
        // completed. The build gate is the actual C# compiler state; treating
        // a trailing asset refresh as a compile failure makes a one-Editor job
        // report a false negative.
        stage.ok = !EditorApplication.isCompiling;
        if (!stage.ok) stage.error = "Unity is still compiling";
        return stage;
    }

    private static StageReport RunBuild(string jobPath, GenerateReport report)
    {
        var stage = new StageReport { name = "build" };
        try
        {
            var result = BuildPlayer.BuildJobFile(jobPath);
            stage.ok = result.ok;
            if (!result.ok) stage.error = result.error;
            string outputPath = result.outputPath;
            if (!string.IsNullOrEmpty(outputPath)) stage.artifacts.Add(outputPath);
        }
        catch (Exception exception)
        {
            stage.ok = false;
            stage.error = exception.ToString();
        }
        return stage;
    }

    private static GenerateReport Finish(GenerateReport report)
    {
        report.ok = report.stages.All(stage => stage.ok);
        if (!report.ok)
            report.errors.AddRange(report.stages.Where(stage => !stage.ok).Select(stage => stage.name + ": " + stage.error));
        return report;
    }

    private static void CopyTree(string source, string target)
    {
        Directory.CreateDirectory(target);
        foreach (string file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
        {
            string relative = file.Substring(source.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string destination = Path.Combine(target, relative);
            string parent = Path.GetDirectoryName(destination);
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            if (!File.Exists(destination) || !FilesEqual(file, destination))
                File.Copy(file, destination, true);
        }
    }

    private static bool FilesEqual(string left, string right)
    {
        FileInfo leftInfo = new FileInfo(left);
        FileInfo rightInfo = new FileInfo(right);
        if (leftInfo.Length != rightInfo.Length) return false;
        using (FileStream leftStream = File.OpenRead(left))
        using (FileStream rightStream = File.OpenRead(right))
        {
            int leftByte;
            while ((leftByte = leftStream.ReadByte()) >= 0)
                if (leftByte != rightStream.ReadByte()) return false;
        }
        return true;
    }

    private static Dictionary<string, string> ParseArgs(string[] argv)
    {
        var result = new Dictionary<string, string>();
        for (int index = 0; index < argv.Length; index++)
        {
            if (!argv[index].StartsWith("--")) continue;
            string key = argv[index].Substring(2);
            string value = index + 1 < argv.Length && !argv[index + 1].StartsWith("--") ? argv[++index] : "";
            result[key] = value;
        }
        return result;
    }

    private static string Get(Dictionary<string, string> args, string key, string fallback)
    {
        if (args.TryGetValue(key, out string value) && !string.IsNullOrEmpty(value)) return value;
        return A3GameForgeEditorBridge.GetArgument(key, fallback);
    }

    private static string JsonString(string json, string key, string fallback)
    {
        string marker = "\"" + key + "\"";
        int keyIndex = json.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (keyIndex < 0) return fallback;
        int colon = json.IndexOf(':', keyIndex + marker.Length);
        int start = colon >= 0 ? json.IndexOf('"', colon + 1) : -1;
        int end = start >= 0 ? json.IndexOf('"', start + 1) : -1;
        return start >= 0 && end > start ? json.Substring(start + 1, end - start - 1) : fallback;
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
        Debug.Log("[GenerateGame] report " + json);
    }
}
