// engine_adapters/unity3d/import_generated/ImportGeneratedMaterial.cs
//
// Creates a PBR Material (Standard shader) and binds the supplied textures to
// the standard shader property slots. Optionally assigns the material to one
// or more mesh assets.
//
// Editor script — copy to <UnityProject>/Assets/Editor/.
//
// CLI:
//     Unity -batchmode -quit -projectPath <proj> \
//           -executeMethod ImportGeneratedMaterial.RunFromCLI \
//           --job <abs path to job.json> \
//           --report <abs path to material_report.json>
//
// job.json keys: src, dest, asset_id, mesh_assets
//
// Texture paths are also read from the job JSON using friendly names that map
// to shader properties:
//     albedo     → _MainTex
//     normal     → _BumpMap
//     metallic   → _Metallic
//     gloss      → _GlossMap
//     occlusion  → _OcclusionMap
//     emission   → _EmissionMap
//
// 'src' is a directory against which relative texture paths are resolved.

using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class ImportGeneratedMaterial
{
    [Serializable]
    public class MaterialReport
    {
        public bool ok;
        public string materialPath = "";
        public int boundTextures;
        public int boundMeshAssetCount;
        public List<string> modifiedMeshAssets = new List<string>();
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    // Shader property name → friendly JSON key, in bind order.
    static readonly string[][] TextureSlots =
    {
        new[] { "_MainTex",      "albedo" },
        new[] { "_BumpMap",      "normal" },
        new[] { "_Metallic",     "metallic" },
        new[] { "_GlossMap",     "gloss" },
        new[] { "_OcclusionMap", "occlusion" },
        new[] { "_EmissionMap",  "emission" },
    };

    // ── CLI entry point ──────────────────────────────────────────────────────

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        var report = new MaterialReport();
        string reportPath = Get(args, "report", null);

        try
        {
            string src = GetJobValue(args, "src", null);
            string dest = GetJobValue(args, "dest", "Assets/Generated/Materials");
            string assetId = GetJobValue(args, "asset_id", null);
            string meshAssets = GetJobValue(args, "mesh_assets", null);

            // Collect texture paths from the job JSON. Each slot tries the
            // friendly name first, then the raw shader property name.
            var texturePaths = new Dictionary<string, string>();
            foreach (var slot in TextureSlots)
            {
                string shaderProp = slot[0];
                string friendlyName = slot[1];
                string path = GetJobValue(args, friendlyName, null);
                if (string.IsNullOrEmpty(path))
                    path = GetJobValue(args, shaderProp, null);
                if (!string.IsNullOrEmpty(path))
                    texturePaths[shaderProp] = path;
            }

            report = CreateMaterial(src, dest, assetId, meshAssets, texturePaths);
        }
        catch (Exception e)
        {
            report.ok = false;
            report.error = e.ToString();
            Debug.LogError("[ImportGeneratedMaterial] " + e);
        }

        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    // ── Create material ───────────────────────────────────────────────────────

    /// <summary>
    /// Create a PBR material with the Standard shader, copy and bind the
    /// supplied textures, and optionally assign the material to mesh assets.
    /// </summary>
    /// <param name="srcDir">Directory against which relative texture paths are
    /// resolved. May be null if all texture paths are absolute.</param>
    /// <param name="destFolder">Project-relative folder for the material asset.</param>
    /// <param name="assetId">Material name / identifier.</param>
    /// <param name="meshAssets">Comma- or semicolon-separated list of prefab/mesh
    /// asset paths to assign the material to.</param>
    /// <param name="texturePaths">Map of shader property names to texture file paths.</param>
    public static MaterialReport CreateMaterial(
        string srcDir,
        string destFolder = "Assets/Generated/Materials",
        string assetId = null,
        string meshAssets = null,
        Dictionary<string, string> texturePaths = null)
    {
        var report = new MaterialReport();

        // 1. Determine the material name.
        string matName = !string.IsNullOrEmpty(assetId)
            ? assetId
            : (!string.IsNullOrEmpty(srcDir) ? Path.GetFileName(srcDir) : "GeneratedMaterial");
        matName = SanitizeName(matName);

        // 2. Find the Standard shader. Fall back through common alternatives
        //    so the script still produces something usable on URP / HDRP projects.
        var shader = Shader.Find("Standard");
        if (shader == null)
        {
            report.warnings.Add("Standard shader not found; trying URP Lit");
            shader = Shader.Find("Universal Render Pipeline/Lit");
        }
        if (shader == null)
        {
            report.warnings.Add("URP Lit shader not found; trying HDRP Lit");
            shader = Shader.Find("HDRP/Lit");
        }
        if (shader == null)
        {
            report.warnings.Add("No PBR shader found; falling back to Diffuse");
            shader = Shader.Find("Diffuse");
        }
        if (shader == null)
            throw new InvalidOperationException("no usable shader found in the project");

        var material = new Material(shader) { name = matName };
        string shaderName = shader.name;

        // Treat a source file as the directory containing the texture task.
        // This keeps relative texture descriptors valid when the public
        // client resolves a single generated image artifact.
        if (!string.IsNullOrEmpty(srcDir) && File.Exists(srcDir))
            srcDir = Path.GetDirectoryName(srcDir);

        // 3. Bind textures to their shader property slots.
        if (texturePaths != null)
        {
            string texturesFolder = $"{destFolder}/Textures";
            foreach (var slot in TextureSlots)
            {
                string shaderProp = slot[0];
                if (!texturePaths.TryGetValue(shaderProp, out string texPath) ||
                    string.IsNullOrEmpty(texPath))
                    continue;

                // Resolve relative paths against srcDir.
                if (!Path.IsPathRooted(texPath) && !string.IsNullOrEmpty(srcDir))
                    texPath = Path.Combine(srcDir, texPath);

                if (!File.Exists(texPath))
                {
                    report.warnings.Add($"texture for {shaderProp} not found at '{texPath}'");
                    continue;
                }

                // Copy the texture into the project and import it.
                Directory.CreateDirectory(texturesFolder);
                string texFileName = SanitizeName(Path.GetFileName(texPath));
                string texAssetPath = $"{texturesFolder}/{texFileName}";
                File.Copy(texPath, texAssetPath, overwrite: true);
                AssetDatabase.ImportAsset(texAssetPath, ImportAssetOptions.ForceUpdate);

                var tex = AssetDatabase.LoadAssetAtPath<Texture>(texAssetPath);
                if (tex == null)
                {
                    report.warnings.Add($"failed to load texture from {texAssetPath}");
                    continue;
                }

                // SetTexture on a non-texture property logs a warning to the
                // console but does not throw; verify the binding took.
                try
                {
                    material.SetTexture(shaderProp, tex);
                    if (material.GetTexture(shaderProp) == tex)
                    {
                        report.boundTextures++;
                    }
                    else
                    {
                        report.warnings.Add(
                            $"'{shaderProp}' did not accept the texture on shader " +
                            $"'{shaderName}' (may not be a texture slot)");
                    }
                }
                catch (Exception ex)
                {
                    report.warnings.Add(
                        $"error binding texture to '{shaderProp}': {ex.Message}");
                }
            }
        }

        // 4. Enable emission keyword if an emission map was bound.
        if (material.HasProperty("_EmissionMap") &&
            material.GetTexture("_EmissionMap") != null)
        {
            material.EnableKeyword("_EMISSION");
            material.globalIlluminationFlags =
                MaterialGlobalIlluminationFlags.RealtimeEmissive;
        }

        // 5. Save the material asset.
        Directory.CreateDirectory(destFolder);
        string matPath = $"{destFolder}/{matName}.mat";
        if (File.Exists(matPath))
        {
            var existing = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            if (existing != null)
            {
                EditorUtility.CopySerialized(material, existing);
                report.warnings.Add($"overwrote existing material {matPath}");
            }
            else
            {
                AssetDatabase.CreateAsset(material, matPath);
            }
        }
        else
        {
            AssetDatabase.CreateAsset(material, matPath);
        }

        report.materialPath = matPath;

        // 6. Optionally assign the material to mesh assets.
        if (!string.IsNullOrEmpty(meshAssets))
        {
            var meshPaths = meshAssets.Split(new[] { ',', ';' },
                StringSplitOptions.RemoveEmptyEntries);
            var savedMat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            foreach (var mp in meshPaths)
            {
                var meshPath = mp.Trim();
                var meshAsset = AssetDatabase.LoadAssetAtPath<GameObject>(meshPath);
                if (meshAsset == null)
                {
                    report.warnings.Add($"mesh_assets: '{meshPath}' not found or not a GameObject");
                    continue;
                }

                var renderers = meshAsset.GetComponentsInChildren<Renderer>(true);
                if (renderers.Length == 0)
                {
                    report.warnings.Add($"mesh_assets: '{meshPath}' has no renderers");
                    continue;
                }

                foreach (var r in renderers)
                {
                    var mats = r.sharedMaterials;
                    for (int i = 0; i < mats.Length; i++)
                        mats[i] = savedMat;
                    r.sharedMaterials = mats;
                }
                EditorUtility.SetDirty(meshAsset);
                report.boundMeshAssetCount++;
                report.modifiedMeshAssets.Add(meshPath);
            }
            if (meshPaths.Length > 0 && report.boundMeshAssetCount == 0)
                throw new FileNotFoundException(
                    "No requested mesh asset could be loaded or modified");
        }

        AssetDatabase.SaveAssets();
        report.ok = true;
        Debug.Log($"[ImportGeneratedMaterial] {report.materialPath}  " +
                  $"bound={report.boundTextures}  warnings={report.warnings.Count}");
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
        Debug.Log("[ImportGeneratedMaterial] report " + json);
    }

    static string SanitizeName(string name)
    {
        foreach (char c in Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
        return name.Replace(' ', '_');
    }
}
