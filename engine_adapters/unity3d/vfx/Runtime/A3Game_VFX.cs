using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace A3Game.EngineAdapters
{
    public enum VFXStyle
    {
        Natural,
        Ink,
        Frost,
        Cyber
    }

    [Serializable]
    public sealed class SmokeOptions
    {
        public bool loop = true;
        public float duration = 5f;
        public float lifetime = 2.8f;
        public float emissionRate = 18f;
        public float riseSpeed = 0.8f;
        public float startSize = 0.55f;
        public float radius = 0.25f;
        public Color color = new Color(0.42f, 0.44f, 0.46f, 0.72f);
        public VFXStyle style = VFXStyle.Natural;
        public Texture2D particleTexture;
        public Material particleMaterial;
        public Vector2Int textureSheetTiles = Vector2Int.one;
        public bool forceAlphaBlend;
    }

    [Serializable]
    public sealed class FireOptions
    {
        public bool loop = true;
        public float duration = 5f;
        public float lifetime = 1.15f;
        public float emissionRate = 42f;
        public float riseSpeed = 1.45f;
        public float startSize = 0.48f;
        public float radius = 0.2f;
        public float intensity = 1f;
        public VFXStyle style = VFXStyle.Natural;
    }

    [Serializable]
    public sealed class BurstOptions
    {
        public int particleCount = 36;
        public float lifetime = 0.8f;
        public float speed = 3.2f;
        public float startSize = 0.3f;
        public float radius = 0.1f;
    }

    /// <summary>
    /// Runtime VFX fallbacks that require no prefabs or third-party packages.
    /// Positions are Unity world-space meters. Call Stop for looping effects.
    /// </summary>
    public static class A3GameVFX
    {
        static readonly Dictionary<bool, Material> Materials = new Dictionary<bool, Material>();
        static Texture2D softParticle;

        public static GameObject SpawnPrefab(
            GameObject prefab,
            Vector3 position,
            Quaternion rotation,
            Vector3 scale,
            Transform parent = null)
        {
            if (prefab == null) throw new ArgumentNullException(nameof(prefab));
            var instance = UnityEngine.Object.Instantiate(prefab, position, rotation, parent);
            instance.name = "AAAGF_" + prefab.name;
            instance.transform.localScale = scale;
            foreach (var ps in instance.GetComponentsInChildren<ParticleSystem>())
                ps.Play(true);
            return instance;
        }

        public static GameObject SpawnSmoke(
            Vector3 position, SmokeOptions options = null, Transform parent = null)
        {
            options = options ?? new SmokeOptions();
            var root = CreateRoot("AAAGF_Smoke", position, parent);
            var ps = CreateSystem(root.transform, "smoke", false);
            if (options.particleMaterial != null)
            {
                var renderer = ps.GetComponent<ParticleSystemRenderer>();
                renderer.sharedMaterial = options.forceAlphaBlend
                    ? CreateAlphaBlendedMaterial(options.particleMaterial)
                    : options.particleMaterial;
            }
            else if (options.particleTexture != null)
            {
                var renderer = ps.GetComponent<ParticleSystemRenderer>();
                renderer.sharedMaterial = CreateMaterial(
                    false, options.particleTexture, "AAAGF_TexturedSmoke");
            }
            if (options.textureSheetTiles.x > 1 || options.textureSheetTiles.y > 1)
            {
                var sheet = ps.textureSheetAnimation;
                sheet.enabled = true;
                sheet.mode = ParticleSystemAnimationMode.Grid;
                sheet.animation = ParticleSystemAnimationType.WholeSheet;
                sheet.numTilesX = Mathf.Max(1, options.textureSheetTiles.x);
                sheet.numTilesY = Mathf.Max(1, options.textureSheetTiles.y);
                sheet.frameOverTime = new ParticleSystem.MinMaxCurve(
                    1f, AnimationCurve.Linear(0f, 0f, 1f, 1f));
                sheet.cycleCount = 1;
            }
            var main = ps.main;
            main.loop = options.loop;
            main.duration = Mathf.Max(0.05f, options.duration);
            main.startLifetime = new ParticleSystem.MinMaxCurve(
                options.lifetime * 0.75f, options.lifetime * 1.25f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(
                options.riseSpeed * 0.65f, options.riseSpeed * 1.25f);
            main.startSize = new ParticleSystem.MinMaxCurve(
                options.startSize * 0.65f, options.startSize * 1.3f);
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;

            var emission = ps.emission;
            emission.rateOverTime = options.emissionRate;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.radius = options.radius;
            shape.angle = 10f;
            ps.transform.localRotation = Quaternion.Euler(-90f, 0f, 0f);

            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = 0.45f;
            noise.frequency = 0.55f;
            noise.scrollSpeed = 0.18f;

            SetSizeCurve(ps, new AnimationCurve(
                new Keyframe(0f, 0.45f), new Keyframe(0.35f, 0.9f), new Keyframe(1f, 1.55f)));
            SetColorGradient(ps, SmokeGradient(options.color, options.style));
            AddStyleAccent(root.transform, options.style, options.loop, options.duration);
            PlayAndScheduleCleanup(root, ps, options.loop, options.duration, options.lifetime);
            return root;
        }

        public static GameObject SpawnFire(
            Vector3 position, FireOptions options = null, Transform parent = null)
        {
            options = options ?? new FireOptions();
            var root = CreateRoot("AAAGF_Fire", position, parent);
            var ps = CreateSystem(root.transform, "fire", true);
            ConfigureFire(ps, options, options.loop, 0);
            AddStyleAccent(root.transform, options.style, options.loop, options.duration);
            PlayAndScheduleCleanup(root, ps, options.loop, options.duration, options.lifetime);
            return root;
        }

        public static GameObject SpawnExplosion(
            Vector3 position, BurstOptions options = null, Transform parent = null)
        {
            options = options ?? new BurstOptions();
            var root = CreateRoot("AAAGF_Explosion", position, parent);

            var fire = CreateSystem(root.transform, "fire_burst", true);
            ConfigureBurst(fire, options, FireGradient(1f, VFXStyle.Natural), true, options.particleCount);

            var smoke = CreateSystem(root.transform, "smoke_burst", false);
            var smokeOptions = new BurstOptions
            {
                particleCount = Mathf.Max(6, options.particleCount / 3),
                lifetime = options.lifetime * 2f,
                speed = options.speed * 0.45f,
                startSize = options.startSize * 1.6f,
                radius = options.radius
            };
            ConfigureBurst(
                smoke, smokeOptions, SmokeGradient(
                    new Color(0.35f, 0.35f, 0.35f, 0.7f), VFXStyle.Natural),
                false, smokeOptions.particleCount);

            fire.Play();
            smoke.Play();
            if (Application.isPlaying)
                UnityEngine.Object.Destroy(
                    root, Mathf.Max(options.lifetime, smokeOptions.lifetime) * 1.5f);
            return root;
        }

        public static GameObject SpawnDust(
            Vector3 position, BurstOptions options = null, Transform parent = null)
        {
            options = options ?? new BurstOptions
            {
                particleCount = 10,
                lifetime = 0.9f,
                speed = 0.6f,
                startSize = 0.22f,
                radius = 0.25f
            };
            var root = CreateRoot("AAAGF_Dust", position, parent);
            var ps = CreateSystem(root.transform, "dust", false);
            ConfigureBurst(ps, options, DustGradient(), false, options.particleCount);
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Hemisphere;
            ps.transform.localRotation = Quaternion.Euler(-90f, 0f, 0f);
            ps.Play();
            if (Application.isPlaying)
                UnityEngine.Object.Destroy(root, options.lifetime * 1.5f);
            return root;
        }

        public static GameObject SpawnInkSmoke(Vector3 position, Transform parent = null)
        {
            return SpawnSmoke(position, new SmokeOptions
            {
                style = VFXStyle.Ink,
                color = new Color(0.08f, 0.09f, 0.1f, 0.9f),
                emissionRate = 23f,
                riseSpeed = 0.55f,
                startSize = 0.7f
            }, parent);
        }

        public static GameObject SpawnFrostFire(Vector3 position, Transform parent = null)
        {
            return SpawnFire(position, new FireOptions
            {
                style = VFXStyle.Frost,
                intensity = 0.9f,
                riseSpeed = 0.9f,
                emissionRate = 34f
            }, parent);
        }

        public static GameObject SpawnCyberFire(Vector3 position, Transform parent = null)
        {
            return SpawnFire(position, new FireOptions
            {
                style = VFXStyle.Cyber,
                intensity = 1.1f,
                lifetime = 0.75f,
                emissionRate = 48f
            }, parent);
        }

        public static void Stop(GameObject effectRoot, bool immediate = false)
        {
            if (effectRoot == null) return;
            var behavior = immediate
                ? ParticleSystemStopBehavior.StopEmittingAndClear
                : ParticleSystemStopBehavior.StopEmitting;
            foreach (var ps in effectRoot.GetComponentsInChildren<ParticleSystem>())
                ps.Stop(true, behavior);
            if (!immediate) return;
            if (Application.isPlaying) UnityEngine.Object.Destroy(effectRoot);
            else UnityEngine.Object.DestroyImmediate(effectRoot);
        }

        static GameObject CreateRoot(string name, Vector3 position, Transform parent)
        {
            var root = new GameObject(name);
            if (parent != null) root.transform.SetParent(parent, true);
            root.transform.position = position;
            return root;
        }

        static ParticleSystem CreateSystem(Transform parent, string name, bool additive)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var ps = go.AddComponent<ParticleSystem>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.playOnAwake = false;
            main.maxParticles = 512;
            var renderer = go.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.sharedMaterial = GetMaterial(additive);
            return ps;
        }

        static void ConfigureFire(ParticleSystem ps, FireOptions options, bool loop, int burstCount)
        {
            var main = ps.main;
            main.loop = loop;
            main.duration = Mathf.Max(0.05f, options.duration);
            main.startLifetime = new ParticleSystem.MinMaxCurve(
                options.lifetime * 0.75f, options.lifetime * 1.2f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(
                options.riseSpeed * 0.7f, options.riseSpeed * 1.25f);
            main.startSize = new ParticleSystem.MinMaxCurve(
                options.startSize * 0.6f, options.startSize * 1.2f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;

            var emission = ps.emission;
            emission.rateOverTime = burstCount > 0 ? 0f : options.emissionRate;
            if (burstCount > 0)
                emission.SetBursts(new[] { MakeBurst(burstCount) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.radius = options.radius;
            shape.angle = 12f;
            ps.transform.localRotation = Quaternion.Euler(-90f, 0f, 0f);

            var noise = ps.noise;
            noise.enabled = true;
            noise.strength = 0.35f;
            noise.frequency = 1.6f;
            SetSizeCurve(ps, new AnimationCurve(
                new Keyframe(0f, 0.55f), new Keyframe(0.3f, 1f), new Keyframe(1f, 0.15f)));
            SetColorGradient(ps, FireGradient(options.intensity, options.style));
        }

        static void AddStyleAccent(
            Transform parent, VFXStyle style, bool loop, float duration)
        {
            if (style == VFXStyle.Natural) return;
            var ps = CreateSystem(parent, "style_accent", style != VFXStyle.Ink);
            var main = ps.main;
            main.loop = loop;
            main.duration = Mathf.Max(0.05f, duration);
            main.startLifetime = style == VFXStyle.Ink
                ? new ParticleSystem.MinMaxCurve(0.5f, 1.1f)
                : new ParticleSystem.MinMaxCurve(0.18f, 0.55f);
            main.startSpeed = style == VFXStyle.Ink
                ? new ParticleSystem.MinMaxCurve(0.15f, 0.5f)
                : new ParticleSystem.MinMaxCurve(0.7f, 1.8f);
            main.startSize = style == VFXStyle.Ink
                ? new ParticleSystem.MinMaxCurve(0.04f, 0.16f)
                : new ParticleSystem.MinMaxCurve(0.025f, 0.09f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var emission = ps.emission;
            emission.rateOverTime = style == VFXStyle.Cyber ? 18f : 9f;
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.3f;
            var noise = ps.noise;
            noise.enabled = true;
            noise.frequency = style == VFXStyle.Cyber ? 4f : 1.2f;
            noise.strength = style == VFXStyle.Ink ? 0.25f : 0.55f;
            SetSizeCurve(ps, new AnimationCurve(
                new Keyframe(0f, 0.25f), new Keyframe(0.2f, 1f), new Keyframe(1f, 0f)));
            SetColorGradient(ps, AccentGradient(style));
            ps.Play();
        }

        static void ConfigureBurst(
            ParticleSystem ps, BurstOptions options, Gradient gradient, bool additive, int count)
        {
            var main = ps.main;
            main.loop = false;
            main.duration = 0.05f;
            main.startLifetime = new ParticleSystem.MinMaxCurve(
                options.lifetime * 0.75f, options.lifetime * 1.25f);
            main.startSpeed = new ParticleSystem.MinMaxCurve(
                options.speed * 0.7f, options.speed * 1.25f);
            main.startSize = new ParticleSystem.MinMaxCurve(
                options.startSize * 0.65f, options.startSize * 1.35f);
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            var emission = ps.emission;
            emission.rateOverTime = 0f;
            emission.SetBursts(new[] { MakeBurst(count) });
            var shape = ps.shape;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = options.radius;
            SetSizeCurve(ps, new AnimationCurve(
                new Keyframe(0f, 0.55f), new Keyframe(0.25f, 1f), new Keyframe(1f, 1.4f)));
            SetColorGradient(ps, gradient);
            ps.GetComponent<ParticleSystemRenderer>().sharedMaterial = GetMaterial(additive);
        }

        static ParticleSystem.Burst MakeBurst(int count)
        {
            return new ParticleSystem.Burst(0f, (short)Mathf.Clamp(count, 1, short.MaxValue));
        }

        static void PlayAndScheduleCleanup(
            GameObject root, ParticleSystem ps, bool loop, float duration, float lifetime)
        {
            ps.Play();
            if (!loop && Application.isPlaying)
                UnityEngine.Object.Destroy(root, Mathf.Max(0.05f, duration) + lifetime * 1.5f);
        }

        static void SetSizeCurve(ParticleSystem ps, AnimationCurve curve)
        {
            var size = ps.sizeOverLifetime;
            size.enabled = true;
            size.size = new ParticleSystem.MinMaxCurve(1f, curve);
        }

        static void SetColorGradient(ParticleSystem ps, Gradient gradient)
        {
            var color = ps.colorOverLifetime;
            color.enabled = true;
            color.color = new ParticleSystem.MinMaxGradient(gradient);
        }

        static Gradient FireGradient(float intensity, VFXStyle style)
        {
            intensity = Mathf.Max(0.1f, intensity);
            var gradient = new Gradient();
            var core = Color.white;
            var primary = new Color(1f, 0.72f, 0.18f);
            var secondary = new Color(1f, 0.16f, 0.015f);
            var tail = new Color(0.18f, 0.01f, 0f);
            if (style == VFXStyle.Ink)
            {
                core = new Color(0.9f, 0.92f, 0.9f);
                primary = new Color(0.32f, 0.34f, 0.33f);
                secondary = new Color(0.08f, 0.09f, 0.09f);
                tail = Color.black;
            }
            else if (style == VFXStyle.Frost)
            {
                core = new Color(0.95f, 1f, 1f);
                primary = new Color(0.35f, 0.9f, 1f);
                secondary = new Color(0.12f, 0.38f, 1f);
                tail = new Color(0.03f, 0.08f, 0.25f);
            }
            else if (style == VFXStyle.Cyber)
            {
                core = new Color(0.82f, 1f, 1f);
                primary = new Color(0.05f, 0.95f, 1f);
                secondary = new Color(1f, 0.05f, 0.72f);
                tail = new Color(0.18f, 0.01f, 0.28f);
            }
            gradient.SetKeys(
                new[]
                {
                    new GradientColorKey(core * intensity, 0f),
                    new GradientColorKey(primary * intensity, 0.3f),
                    new GradientColorKey(secondary * intensity, 0.72f),
                    new GradientColorKey(tail, 1f)
                },
                new[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(1f, 0.08f),
                    new GradientAlphaKey(0.8f, 0.72f),
                    new GradientAlphaKey(0f, 1f)
                });
            return gradient;
        }

        static Gradient SmokeGradient(Color color, VFXStyle style)
        {
            if (style == VFXStyle.Ink) color = new Color(0.06f, 0.07f, 0.075f, 0.9f);
            else if (style == VFXStyle.Frost) color = new Color(0.52f, 0.82f, 0.9f, 0.6f);
            else if (style == VFXStyle.Cyber) color = new Color(0.15f, 0.75f, 0.9f, 0.58f);
            var gradient = new Gradient();
            gradient.SetKeys(
                new[]
                {
                    new GradientColorKey(color, 0f),
                    new GradientColorKey(new Color(
                        color.r * 0.75f, color.g * 0.75f, color.b * 0.75f), 1f)
                },
                new[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(color.a, 0.18f),
                    new GradientAlphaKey(color.a * 0.45f, 0.7f),
                    new GradientAlphaKey(0f, 1f)
                });
            return gradient;
        }

        static Gradient DustGradient()
        {
            return SmokeGradient(
                new Color(0.58f, 0.45f, 0.3f, 0.52f), VFXStyle.Natural);
        }

        static Gradient AccentGradient(VFXStyle style)
        {
            var gradient = new Gradient();
            var primary = style == VFXStyle.Ink
                ? new Color(0.02f, 0.025f, 0.03f)
                : style == VFXStyle.Frost
                    ? new Color(0.72f, 0.96f, 1f)
                    : new Color(0.05f, 1f, 0.95f);
            var secondary = style == VFXStyle.Cyber
                ? new Color(1f, 0.04f, 0.72f)
                : Color.white;
            gradient.SetKeys(
                new[]
                {
                    new GradientColorKey(primary, 0f),
                    new GradientColorKey(secondary, 0.65f),
                    new GradientColorKey(primary, 1f)
                },
                new[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(1f, 0.15f),
                    new GradientAlphaKey(0f, 1f)
                });
            return gradient;
        }

        static Material GetMaterial(bool additive)
        {
            if (Materials.TryGetValue(additive, out var cached) && cached != null)
                return cached;
            var material = CreateMaterial(
                additive,
                GetSoftParticle(),
                additive ? "AAAGF_Additive" : "AAAGF_Alpha");
            Materials[additive] = material;
            return material;
        }

        static Material CreateMaterial(bool additive, Texture texture, string name)
        {
            var shader = Shader.Find("A3Game/SoftParticle")
                         ?? Shader.Find("Universal Render Pipeline/Particles/Unlit")
                         ?? Shader.Find("Particles/Standard Unlit")
                         ?? Shader.Find("Legacy Shaders/Particles/Additive")
                         ?? Shader.Find("Sprites/Default");
            if (shader == null)
                throw new InvalidOperationException("No compatible particle shader is available");

            var material = new Material(shader) { name = name };
            material.mainTexture = texture;
            if (material.HasProperty("_BaseMap")) material.SetTexture("_BaseMap", texture);
            if (shader.name == "A3Game/SoftParticle")
            {
                material.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
                material.SetInt("_DstBlend", (int)(additive ? BlendMode.One : BlendMode.OneMinusSrcAlpha));
                material.SetInt("_ZWrite", 0);
                material.renderQueue = 3000;
            }
            else if (material.HasProperty("_Surface"))
            {
                material.SetFloat("_Surface", 1f);
                material.SetFloat("_Blend", additive ? 2f : 0f);
                material.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
                material.SetInt("_DstBlend", (int)(additive ? BlendMode.One : BlendMode.OneMinusSrcAlpha));
                material.SetInt("_ZWrite", 0);
                material.renderQueue = 3000;
            }
            else if (material.HasProperty("_Mode"))
            {
                material.SetFloat("_Mode", additive ? 4f : 2f);
            }
            return material;
        }

        static Material CreateAlphaBlendedMaterial(Material source)
        {
            var material = new Material(source)
            {
                name = source.name + "_AAAGF_AlphaBlend"
            };
            material.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            material.EnableKeyword("_ALPHABLEND_ON");
            material.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            if (material.HasProperty("_Surface")) material.SetFloat("_Surface", 1f);
            if (material.HasProperty("_Blend")) material.SetFloat("_Blend", 0f);
            if (material.HasProperty("_SrcBlend"))
                material.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
            if (material.HasProperty("_DstBlend"))
                material.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
            if (material.HasProperty("_SrcBlendAlpha"))
                material.SetInt("_SrcBlendAlpha", (int)BlendMode.One);
            if (material.HasProperty("_DstBlendAlpha"))
                material.SetInt("_DstBlendAlpha", (int)BlendMode.OneMinusSrcAlpha);
            if (material.HasProperty("_ZWrite")) material.SetInt("_ZWrite", 0);
            material.SetOverrideTag("RenderType", "Transparent");
            material.renderQueue = 3000;
            return material;
        }

        static Texture2D GetSoftParticle()
        {
            if (softParticle != null) return softParticle;
            const int size = 64;
            softParticle = new Texture2D(size, size, TextureFormat.RGBA32, false)
            {
                name = "AAAGF_SoftParticle",
                filterMode = FilterMode.Bilinear,
                wrapMode = TextureWrapMode.Clamp
            };
            var pixels = new Color[size * size];
            for (var y = 0; y < size; y++)
            for (var x = 0; x < size; x++)
            {
                var dx = (x + 0.5f) / size * 2f - 1f;
                var dy = (y + 0.5f) / size * 2f - 1f;
                var alpha = Mathf.Clamp01(1f - Mathf.Sqrt(dx * dx + dy * dy));
                alpha = alpha * alpha * (3f - 2f * alpha);
                pixels[y * size + x] = new Color(1f, 1f, 1f, alpha);
            }
            softParticle.SetPixels(pixels);
            softParticle.Apply(false, true);
            return softParticle;
        }
    }
}
