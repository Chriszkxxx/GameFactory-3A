// Shared post-import repair for FBX assets that embed textures but retain
// absolute source-machine texture paths. Unity's ModelImporter can extract
// those textures and remap the embedded material to project-local assets.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class RepairImportedModelMaterials
{
    public sealed class Result
    {
        public int extractedTextures;
        public int generatedMaterials;
        public int remappedMaterials;
        public int boundTextures;
        public readonly List<string> warnings = new List<string>();
    }

    public static Result Repair(string assetPath, string assetName)
    {
        var result = new Result();
        var importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
        if (importer == null)
        {
            result.warnings.Add("No ModelImporter available for material repair: " + assetPath);
            return result;
        }

        string textureFolder = "Assets/Generated/Textures/" + Sanitize(assetName);
        string materialFolder = "Assets/Generated/Materials/" + Sanitize(assetName);
        EnsureFolder(textureFolder);
        EnsureFolder(materialFolder);

        // ImportViaMaterialDescription is required for embedded FBX material
        // slots to be visible to ExtractTextures and AddRemap.
        importer.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
        importer.ExtractTextures(textureFolder);
        importer.SaveAndReimport();
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

        List<Texture2D> extracted = AssetDatabase.FindAssets("t:Texture2D", new[] { textureFolder })
            .Select(AssetDatabase.GUIDToAssetPath)
            .Select(AssetDatabase.LoadAssetAtPath<Texture2D>)
            .Where(texture => texture != null)
            .ToList();
        result.extractedTextures = extracted.Count;

        Material[] embedded = AssetDatabase.LoadAllAssetsAtPath(assetPath)
            .OfType<Material>()
            .ToArray();
        if (embedded.Length == 0)
        {
            if (extracted.Count == 0)
                result.warnings.Add("FBX has no embedded materials or extracted textures");
            return result;
        }

        Shader shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
        if (shader == null)
        {
            result.warnings.Add("No URP/Lit or Standard shader is available for material repair");
            return result;
        }

        foreach (Material source in embedded)
        {
            string materialName = Sanitize(assetName + "_" + source.name);
            string materialPath = materialFolder + "/" + materialName + ".mat";
            Material target = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (target == null)
            {
                target = new Material(shader) { name = materialName };
                AssetDatabase.CreateAsset(target, materialPath);
                result.generatedMaterials++;
            }
            else if (target.shader == null || target.shader.name == "Hidden/InternalErrorShader")
            {
                target.shader = shader;
            }

            int bound = BindTextures(target, source, extracted);
            result.boundTextures += bound;
            EditorUtility.SetDirty(target);
            importer.AddRemap(
                new AssetImporter.SourceAssetIdentifier(typeof(Material), source.name),
                target);
            result.remappedMaterials++;
        }

        importer.SaveAndReimport();
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        if (result.extractedTextures == 0)
            result.warnings.Add("No texture files were extracted from the embedded FBX payload");
        if (result.boundTextures == 0)
            result.warnings.Add("Embedded materials were remapped but no texture slot was bound");
        return result;
    }

    private static int BindTextures(Material target, Material source, IEnumerable<Texture2D> extracted)
    {
        int count = 0;
        Texture baseMap = FirstTexture(source, extracted, "_BaseMap", "_MainTex", "diffuse", "albedo", "texture_pbr");
        Texture normal = FirstTexture(source, extracted, "_BumpMap", "_NormalMap", "normal");
        Texture metallic = FirstTexture(source, extracted, "_MetallicGlossMap", "_Metallic", "metallic", "roughness");
        Texture occlusion = FirstTexture(source, extracted, "_OcclusionMap", "occlusion", "ao");

        if (baseMap != null) { SetTextureIfPresent(target, "_BaseMap", baseMap); SetTextureIfPresent(target, "_MainTex", baseMap); count++; }
        if (normal != null) { SetTextureIfPresent(target, "_BumpMap", normal); SetTextureIfPresent(target, "_NormalMap", normal); target.EnableKeyword("_NORMALMAP"); count++; }
        if (metallic != null) { SetTextureIfPresent(target, "_MetallicGlossMap", metallic); SetTextureIfPresent(target, "_MetallicMap", metallic); target.EnableKeyword("_METALLICSPECGLOSSMAP"); count++; }
        if (occlusion != null) { SetTextureIfPresent(target, "_OcclusionMap", occlusion); count++; }
        if (source != null && source.HasProperty("_Color") && target.HasProperty("_BaseColor")) target.SetColor("_BaseColor", source.color);
        if (source != null && source.HasProperty("_Color") && target.HasProperty("_Color")) target.SetColor("_Color", source.color);
        return count;
    }

    private static Texture FirstTexture(Material source, IEnumerable<Texture2D> extracted, params string[] names)
    {
        foreach (string name in names)
        {
            if (name.StartsWith("_", StringComparison.Ordinal) && source != null && source.HasProperty(name))
            {
                Texture assigned = source.GetTexture(name);
                if (assigned != null) return assigned;
            }
        }
        foreach (string name in names.Where(value => !value.StartsWith("_", StringComparison.Ordinal)))
        {
            string key = name.ToLowerInvariant();
            Texture2D match = extracted.FirstOrDefault(texture => texture.name.ToLowerInvariant().Contains(key));
            if (match != null) return match;
        }
        return null;
    }

    private static void SetTextureIfPresent(Material material, string property, Texture texture)
    {
        if (material.HasProperty(property)) material.SetTexture(property, texture);
    }

    private static void EnsureFolder(string path)
    {
        string current = "Assets";
        foreach (string part in path.Split('/').Skip(1))
        {
            string next = current + "/" + part;
            if (!AssetDatabase.IsValidFolder(next)) AssetDatabase.CreateFolder(current, part);
            current = next;
        }
    }

    private static string Sanitize(string value)
    {
        foreach (char character in Path.GetInvalidFileNameChars()) value = value.Replace(character, '_');
        return string.IsNullOrWhiteSpace(value) ? "ImportedModel" : value.Replace(' ', '_');
    }
}
