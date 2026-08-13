// Imports a generated image as a concrete Unity Texture2D asset.

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportGeneratedTexture
{
    [Serializable]
    private class TextureJob
    {
        public string src = "";
        public string dest = "Assets/Imported/Textures";
        public string asset_id = "";
        public string texture_type = "Default";
        public bool alpha_is_transparency;
        public bool linear;
        public int max_size = 2048;
    }

    [Serializable]
    private class TextureReport
    {
        public bool ok;
        public string assetPath = "";
        public int width;
        public int height;
        public string format = "";
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    public static void RunFromCLI()
    {
        Dictionary<string, string> args = ParseArgs(Environment.GetCommandLineArgs());
        string reportPath = Get(args, "report", "");
        var report = new TextureReport();
        try
        {
            string jobPath = Get(args, "job", "");
            if (string.IsNullOrEmpty(jobPath) || !File.Exists(jobPath))
                throw new FileNotFoundException("Texture job file was not found", jobPath);
            TextureJob job = JsonUtility.FromJson<TextureJob>(File.ReadAllText(jobPath));
            if (job == null)
                throw new InvalidDataException("Texture job JSON is invalid");
            report = Import(job);
        }
        catch (Exception exception)
        {
            report.ok = false;
            report.error = exception.ToString();
            Debug.LogError("[ImportGeneratedTexture] " + exception);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    private static TextureReport Import(TextureJob job)
    {
        if (!File.Exists(job.src))
            throw new FileNotFoundException("Generated texture was not found", job.src);
        if (string.IsNullOrEmpty(job.dest) ||
            (!job.dest.Equals("Assets") && !job.dest.StartsWith("Assets/")))
            throw new ArgumentException("dest must be an Assets-relative folder");

        string extension = Path.GetExtension(job.src).ToLowerInvariant();
        var supported = new HashSet<string>
        {
            ".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff",
            ".psd", ".exr", ".hdr",
        };
        if (!supported.Contains(extension))
            throw new ArgumentException("Unsupported texture extension: " + extension);

        string name = string.IsNullOrEmpty(job.asset_id)
            ? Path.GetFileNameWithoutExtension(job.src)
            : job.asset_id;
        name = SanitizeName(name);
        Directory.CreateDirectory(job.dest);
        string assetPath = job.dest + "/" + name + extension;
        File.Copy(job.src, assetPath, true);
        AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);

        TextureImporter importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
        if (importer == null)
            throw new InvalidOperationException("Unity did not create a TextureImporter for " + assetPath);
        if (!Enum.TryParse(job.texture_type, true, out TextureImporterType textureType))
            throw new ArgumentException("Unsupported TextureImporterType: " + job.texture_type);
        importer.textureType = textureType;
        importer.alphaIsTransparency = job.alpha_is_transparency;
        importer.sRGBTexture = !job.linear;
        importer.maxTextureSize = Mathf.Clamp(job.max_size, 32, 8192);
        importer.SaveAndReimport();

        Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(assetPath);
        if (texture == null)
            throw new InvalidOperationException("Unity produced no Texture2D for " + assetPath);
        return new TextureReport
        {
            ok = true,
            assetPath = assetPath,
            width = texture.width,
            height = texture.height,
            format = texture.format.ToString(),
        };
    }

    private static string SanitizeName(string value)
    {
        foreach (char invalid in Path.GetInvalidFileNameChars())
            value = value.Replace(invalid, '_');
        return string.IsNullOrWhiteSpace(value) ? "GeneratedTexture" : value.Trim();
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

    private static void WriteReport(TextureReport report, string path)
    {
        string json = JsonUtility.ToJson(report, true);
        if (!string.IsNullOrEmpty(path))
        {
            string parent = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);
            File.WriteAllText(path, json);
        }
        Debug.Log("[ImportGeneratedTexture] report " + json);
    }
}
