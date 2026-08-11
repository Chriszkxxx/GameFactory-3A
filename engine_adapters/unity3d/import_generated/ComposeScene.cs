using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;

public static class ComposeScene
{
    [Serializable]
    private class VectorSpec
    {
        public float x;
        public float y;
        public float z;

        public Vector3 Value => new Vector3(x, y, z);
    }

    [Serializable]
    private class EnvironmentSpec
    {
        public string name = "Environment";
        public string prefab_path = "";
        public VectorSpec position = new VectorSpec();
        public VectorSpec rotation = new VectorSpec();
        public VectorSpec scale = new VectorSpec { x = 1f, y = 1f, z = 1f };
    }

    [Serializable]
    private class FieldSpec
    {
        public string name = "";
        public string kind = "string";
        public string value = "";
        public float number;
        public int integer;
        public bool boolean;
        public VectorSpec vector = new VectorSpec();
        public string asset_path = "";
        public string object_name = "";
    }

    [Serializable]
    private class ComponentSpec
    {
        public string type = "";
        public FieldSpec[] fields;
    }

    [Serializable]
    private class ObjectSpec
    {
        public string name = "GameObject";
        public string prefab_path = "";
        public string parent = "";
        public VectorSpec position = new VectorSpec();
        public VectorSpec rotation = new VectorSpec();
        public VectorSpec scale = new VectorSpec { x = 1f, y = 1f, z = 1f };
        public bool active = true;
        public ComponentSpec[] components;
    }

    [Serializable]
    private class SceneJob
    {
        public string output_scene = "Assets/Scenes/GeneratedGame.unity";
        public string base_scene = "";
        public string world_id = "generated_world";
        public string adapter_type = "";
        public string ui_type = "";
        public string runtime_type = "";
        public string player_prefab = "";
        public string enemy_prefab = "";
        public string weapon_prefab = "";
        public string idle_animation = "";
        public string walk_animation = "";
        public string shoot_animation = "";
        public string reload_animation = "";
        public string death_animation = "";
        public string animator_controller = "Assets/Generated/Animations/FPSCharacter.controller";
        public EnvironmentSpec[] environment_assets;
        public VectorSpec player_spawn = new VectorSpec();
        public VectorSpec player_rotation;
        public VectorSpec[] spawn_points;
        public bool create_ground = true;
        public bool enable_urp = true;
        public bool use_base_scene_camera_rotation = true;
        public bool create_default_camera = true;
        public ObjectSpec[] objects;
    }

    [Serializable]
    private class SceneReport
    {
        public bool ok;
        public string scenePath = "";
        public string baseScenePath = "";
        public string worldId = "";
        public string animatorControllerPath = "";
        public string renderPipelinePath = "";
        public int rootObjectCount;
        public int configuredObjectCount;
        public List<string> usedAssetPaths = new List<string>();
        public List<string> dependencies = new List<string>();
        public List<string> warnings = new List<string>();
        public string error = "";
    }

    public static void RunFromCLI()
    {
        var args = ParseArgs(Environment.GetCommandLineArgs());
        string reportPath = Get(args, "report", "");
        var report = new SceneReport();
        try
        {
            string jobPath = Get(args, "job", "");
            if (string.IsNullOrEmpty(jobPath) || !File.Exists(jobPath))
                throw new FileNotFoundException("Scene composition job was not found", jobPath);
            SceneJob job = JsonUtility.FromJson<SceneJob>(File.ReadAllText(jobPath));
            if (job == null) throw new InvalidDataException("Scene composition job is invalid");
            report = Compose(job);
        }
        catch (Exception exception)
        {
            report.ok = false;
            report.error = exception.ToString();
            Debug.LogError("[ComposeScene] " + exception);
        }
        WriteReport(report, reportPath);
        if (Application.isBatchMode)
            EditorApplication.Exit(report.ok ? 0 : 1);
    }

    private static SceneReport Compose(SceneJob job)
    {
        if (string.IsNullOrEmpty(job.output_scene) || !job.output_scene.StartsWith("Assets/"))
            throw new ArgumentException("output_scene must be a project-relative Assets path");
        var report = new SceneReport
        {
            scenePath = job.output_scene,
            baseScenePath = job.base_scene,
            worldId = job.world_id,
        };
        Scene scene;
        Vector3 baseCameraRotation = Vector3.zero;
        if (!string.IsNullOrEmpty(job.base_scene))
        {
            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(job.base_scene) == null)
                throw new FileNotFoundException("Configured base scene was not found", job.base_scene);
            scene = EditorSceneManager.OpenScene(job.base_scene, OpenSceneMode.Single);
            report.usedAssetPaths.Add(job.base_scene);
            Camera baseCamera = UnityEngine.Object.FindObjectOfType<Camera>(true);
            if (baseCamera != null) baseCameraRotation = baseCamera.transform.eulerAngles;
            RemoveExistingCameras();
        }
        else
        {
            scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }

        if (job.enable_urp)
            report.renderPipelinePath = EnsureUniversalRenderPipeline();

        GameObject environmentRoot = new GameObject("Prepared_NoraPrime_Outpost");
        foreach (EnvironmentSpec item in job.environment_assets ?? new EnvironmentSpec[0])
        {
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(item.prefab_path);
            if (prefab == null)
            {
                report.warnings.Add("Environment prefab not found: " + item.prefab_path);
                continue;
            }
            GameObject instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
            if (instance == null) continue;
            instance.name = item.name;
            instance.transform.SetParent(environmentRoot.transform, false);
            instance.transform.localPosition = item.position != null ? item.position.Value : Vector3.zero;
            instance.transform.localRotation = Quaternion.Euler(item.rotation != null ? item.rotation.Value : Vector3.zero);
            Vector3 scale = item.scale != null ? item.scale.Value : Vector3.one;
            instance.transform.localScale = scale == Vector3.zero ? Vector3.one : scale;
            report.usedAssetPaths.Add(item.prefab_path);
        }

        if (job.create_ground)
        {
            GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "ArenaWalkableGround";
            ground.transform.SetParent(environmentRoot.transform, false);
            ground.transform.localScale = new Vector3(6f, 1f, 6f);
            Material material = new Material(Shader.Find("Standard"));
            material.color = new Color(0.12f, 0.15f, 0.17f);
            ground.GetComponent<Renderer>().sharedMaterial = material;
        }

        if (string.IsNullOrEmpty(job.base_scene))
        {
            GameObject lightObject = new GameObject("ArenaKeyLight");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.1f;
            light.color = new Color(0.82f, 0.9f, 1f);
            lightObject.transform.rotation = Quaternion.Euler(48f, -32f, 0f);
        }

        if (job.objects != null && job.objects.Length > 0)
        {
            report.configuredObjectCount = ComposeObjects(job.objects, report);
            if (job.create_default_camera && UnityEngine.Object.FindObjectOfType<Camera>(true) == null)
            {
                GameObject cameraObject = new GameObject("Main Camera");
                Camera camera = cameraObject.AddComponent<Camera>();
                camera.tag = "MainCamera";
                cameraObject.AddComponent<AudioListener>();
                cameraObject.transform.position = new Vector3(0f, 1.7f, -6f);
            }
            SaveScene(job, scene, report);
            return report;
        }

        RuntimeAnimatorController characterController = CreateCharacterController(job);
        report.animatorControllerPath = AssetDatabase.GetAssetPath(characterController);
        report.usedAssetPaths.Add(report.animatorControllerPath);

        GameObject gameplayRoot = new GameObject("FPSArenaGameplay");
        gameplayRoot.transform.position = job.player_spawn != null
            ? job.player_spawn.Value
            : Vector3.zero;
        Type adapterType = FindType(job.adapter_type);
        Component adapter = gameplayRoot.AddComponent(adapterType);

        GameObject playerPrefab = LoadPrefab(job.player_prefab, "player", report);
        GameObject enemyPrefab = LoadPrefab(job.enemy_prefab, "enemy", report);
        GameObject weaponPrefab = LoadPrefab(job.weapon_prefab, "weapon", report);
        Transform[] spawnPoints = CreateSpawnPoints(
            gameplayRoot.transform,
            job.spawn_points);
        MethodInfo configure = adapterType.GetMethod(
            "ConfigureAssets",
            BindingFlags.Instance | BindingFlags.Public);
        if (configure == null)
            throw new MissingMethodException(job.adapter_type, "ConfigureAssets");
        configure.Invoke(adapter, new object[]
        {
            playerPrefab,
            enemyPrefab,
            weaponPrefab,
            spawnPoints,
            characterController,
            characterController,
        });
        MethodInfo configureView = adapterType.GetMethod(
            "ConfigureView",
            BindingFlags.Instance | BindingFlags.Public);
        Vector3 initialView = job.player_rotation != null
            ? job.player_rotation.Value
            : job.use_base_scene_camera_rotation
                ? baseCameraRotation
                : Vector3.zero;
        configureView?.Invoke(adapter, new object[] { initialView });

        GameObject uiRoot = new GameObject("FPSArenaUI");
        uiRoot.AddComponent(FindType(job.ui_type));

        if (!string.IsNullOrEmpty(job.runtime_type))
        {
            GameObject runtimeRoot = new GameObject("A3GameRuntime");
            Component runtime = runtimeRoot.AddComponent(FindType(job.runtime_type));
            MethodInfo initialize = runtime.GetType().GetMethod("Initialize", new[] { typeof(string) });
            initialize?.Invoke(runtime, new object[] { job.world_id });
        }

        SaveScene(job, scene, report);
        return report;
    }

    private static int ComposeObjects(ObjectSpec[] specs, SceneReport report)
    {
        var objects = new Dictionary<string, GameObject>(StringComparer.Ordinal);
        var components = new Dictionary<ComponentSpec, Component>();
        foreach (ObjectSpec spec in specs)
        {
            string name = ObjectName(spec);
            if (objects.ContainsKey(name))
                throw new InvalidOperationException("Scene object names must be unique: " + name);
            GameObject instance;
            if (!string.IsNullOrEmpty(spec.prefab_path))
            {
                GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.prefab_path);
                if (prefab == null)
                    throw new FileNotFoundException("Configured prefab was not found", spec.prefab_path);
                instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
                if (instance == null)
                    throw new InvalidOperationException("Unity could not instantiate " + spec.prefab_path);
                report.usedAssetPaths.Add(spec.prefab_path);
            }
            else
            {
                instance = new GameObject(name);
            }
            instance.name = name;
            instance.transform.position = spec.position != null ? spec.position.Value : Vector3.zero;
            instance.transform.rotation = Quaternion.Euler(
                spec.rotation != null ? spec.rotation.Value : Vector3.zero);
            Vector3 scale = spec.scale != null ? spec.scale.Value : Vector3.one;
            instance.transform.localScale = scale == Vector3.zero ? Vector3.one : scale;
            objects.Add(name, instance);
        }

        foreach (ObjectSpec spec in specs)
        {
            GameObject instance = objects[ObjectName(spec)];
            if (!string.IsNullOrEmpty(spec.parent))
            {
                if (!objects.TryGetValue(spec.parent, out GameObject parent))
                    throw new InvalidOperationException(
                        "Scene object parent was not found: " + spec.parent);
                instance.transform.SetParent(parent.transform, true);
            }
            foreach (ComponentSpec componentSpec in spec.components ?? new ComponentSpec[0])
            {
                Type type = FindType(componentSpec.type);
                Component component = instance.GetComponent(type) ?? instance.AddComponent(type);
                components.Add(componentSpec, component);
            }
        }

        // Resolve fields only after every component exists so references may
        // point forward to components declared later in the scene spec.
        foreach (ObjectSpec spec in specs)
        {
            GameObject instance = objects[ObjectName(spec)];
            foreach (ComponentSpec componentSpec in spec.components ?? new ComponentSpec[0])
            {
                Component component = components[componentSpec];
                foreach (FieldSpec field in componentSpec.fields ?? new FieldSpec[0])
                    AssignMember(component, field, objects, report);
            }
            instance.SetActive(spec.active);
        }
        return objects.Count;
    }

    private static string ObjectName(ObjectSpec spec)
    {
        return string.IsNullOrWhiteSpace(spec.name) ? "GameObject" : spec.name.Trim();
    }

    private static void AssignMember(
        Component component,
        FieldSpec spec,
        Dictionary<string, GameObject> objects,
        SceneReport report)
    {
        if (string.IsNullOrWhiteSpace(spec.name))
            throw new ArgumentException("Component field name is required");
        const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        Type componentType = component.GetType();
        FieldInfo field = componentType.GetField(spec.name, flags);
        PropertyInfo property = field == null ? componentType.GetProperty(spec.name, flags) : null;
        Type valueType = field != null ? field.FieldType : property?.PropertyType;
        if (valueType == null || (property != null && !property.CanWrite))
            throw new MissingMemberException(componentType.FullName, spec.name);
        object value = ResolveFieldValue(spec, valueType, objects, report);
        if (field != null)
            field.SetValue(component, value);
        else
            property.SetValue(component, value);
        EditorUtility.SetDirty(component);
    }

    private static object ResolveFieldValue(
        FieldSpec spec,
        Type valueType,
        Dictionary<string, GameObject> objects,
        SceneReport report)
    {
        string kind = string.IsNullOrEmpty(spec.kind) ? "string" : spec.kind.ToLowerInvariant();
        switch (kind)
        {
            case "asset":
                UnityEngine.Object asset = AssetDatabase.LoadAssetAtPath(spec.asset_path, valueType);
                if (asset == null)
                    throw new FileNotFoundException(
                        "Component asset field could not be resolved", spec.asset_path);
                report.usedAssetPaths.Add(spec.asset_path);
                return asset;
            case "object":
                if (!objects.TryGetValue(spec.object_name, out GameObject target))
                    throw new InvalidOperationException(
                        "Component object field could not be resolved: " + spec.object_name);
                if (valueType == typeof(GameObject)) return target;
                if (valueType == typeof(Transform)) return target.transform;
                if (typeof(Component).IsAssignableFrom(valueType))
                {
                    Component referenced = target.GetComponent(valueType);
                    if (referenced == null)
                        throw new MissingComponentException(
                            spec.object_name + " has no " + valueType.FullName);
                    return referenced;
                }
                throw new InvalidCastException("Object reference cannot be assigned to " + valueType.FullName);
            case "vector3":
                return spec.vector != null ? spec.vector.Value : Vector3.zero;
            case "bool":
                return spec.boolean;
            case "int":
                return Convert.ChangeType(spec.integer, valueType);
            case "float":
                return Convert.ChangeType(spec.number, valueType);
            case "enum":
                return Enum.Parse(valueType, spec.value, true);
            case "string":
                return spec.value;
            default:
                throw new ArgumentException("Unsupported component field kind: " + spec.kind);
        }
    }

    private static void SaveScene(SceneJob job, Scene scene, SceneReport report)
    {
        string sceneDirectory = Path.GetDirectoryName(job.output_scene);
        if (!string.IsNullOrEmpty(sceneDirectory)) Directory.CreateDirectory(sceneDirectory);
        if (!EditorSceneManager.SaveScene(scene, job.output_scene))
            throw new IOException("Unity could not save scene: " + job.output_scene);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(job.output_scene, true) };
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        report.rootObjectCount = scene.GetRootGameObjects().Length;
        report.dependencies = AssetDatabase.GetDependencies(job.output_scene, true).ToList();
        report.ok = File.Exists(Path.GetFullPath(job.output_scene));
        if (!report.ok) report.error = "Saved scene file was not found";
    }

    private static RuntimeAnimatorController CreateCharacterController(SceneJob job)
    {
        if (string.IsNullOrEmpty(job.animator_controller) ||
            !job.animator_controller.StartsWith("Assets/") ||
            !job.animator_controller.EndsWith(".controller"))
            throw new ArgumentException("animator_controller must be an Assets-relative .controller path");

        AnimationClip idle = LoadClip(job.idle_animation, "idle");
        AnimationClip walk = LoadClip(job.walk_animation, "walk");
        AnimationClip shoot = LoadClip(job.shoot_animation, "shoot");
        AnimationClip reload = LoadClip(job.reload_animation, "reload");
        AnimationClip death = LoadClip(job.death_animation, "death");

        string directory = Path.GetDirectoryName(job.animator_controller);
        if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
        if (AssetDatabase.LoadAssetAtPath<RuntimeAnimatorController>(job.animator_controller) != null)
            AssetDatabase.DeleteAsset(job.animator_controller);

        AnimatorController controller = AnimatorController.CreateAnimatorControllerAtPath(
            job.animator_controller);
        controller.AddParameter("Speed", AnimatorControllerParameterType.Float);
        controller.AddParameter("Shoot", AnimatorControllerParameterType.Trigger);
        controller.AddParameter("Reload", AnimatorControllerParameterType.Trigger);
        controller.AddParameter("Death", AnimatorControllerParameterType.Trigger);

        AnimatorStateMachine machine = controller.layers[0].stateMachine;
        AnimatorState idleState = machine.AddState("Idle");
        AnimatorState walkState = machine.AddState("Walk");
        AnimatorState shootState = machine.AddState("Shoot");
        AnimatorState reloadState = machine.AddState("Reload");
        AnimatorState deathState = machine.AddState("Death");
        idleState.motion = idle;
        walkState.motion = walk;
        shootState.motion = shoot;
        reloadState.motion = reload;
        deathState.motion = death;
        machine.defaultState = idleState;

        AnimatorStateTransition toWalk = idleState.AddTransition(walkState);
        toWalk.hasExitTime = false;
        toWalk.duration = 0.12f;
        toWalk.AddCondition(AnimatorConditionMode.Greater, 0.1f, "Speed");
        AnimatorStateTransition toIdle = walkState.AddTransition(idleState);
        toIdle.hasExitTime = false;
        toIdle.duration = 0.12f;
        toIdle.AddCondition(AnimatorConditionMode.Less, 0.1f, "Speed");

        AddTriggeredTransition(machine, shootState, "Shoot");
        AddTriggeredTransition(machine, reloadState, "Reload");
        AddTriggeredTransition(machine, deathState, "Death");
        AddExitTransition(shootState, idleState);
        AddExitTransition(reloadState, idleState);
        AssetDatabase.SaveAssets();
        return controller;
    }

    private static void AddTriggeredTransition(
        AnimatorStateMachine machine,
        AnimatorState target,
        string trigger)
    {
        AnimatorStateTransition transition = machine.AddAnyStateTransition(target);
        transition.hasExitTime = false;
        transition.duration = 0.08f;
        transition.canTransitionToSelf = false;
        transition.AddCondition(AnimatorConditionMode.If, 0f, trigger);
    }

    private static void AddExitTransition(AnimatorState source, AnimatorState target)
    {
        AnimatorStateTransition transition = source.AddTransition(target);
        transition.hasExitTime = true;
        transition.exitTime = 0.9f;
        transition.duration = 0.1f;
    }

    private static AnimationClip LoadClip(string path, string role)
    {
        AnimationClip clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
        if (clip == null)
            throw new FileNotFoundException("Configured " + role + " AnimationClip was not found", path);
        return clip;
    }

    private static void RemoveExistingCameras()
    {
        foreach (Camera camera in UnityEngine.Object.FindObjectsOfType<Camera>(true))
            UnityEngine.Object.DestroyImmediate(camera.gameObject);
        foreach (AudioListener listener in UnityEngine.Object.FindObjectsOfType<AudioListener>(true))
            if (listener != null) UnityEngine.Object.DestroyImmediate(listener);
    }

    private static string EnsureUniversalRenderPipeline()
    {
        const string directory = "Assets/Generated/Rendering";
        const string rendererPath = directory + "/FPSArenaRenderer.asset";
        const string pipelinePath = directory + "/FPSArenaURP.asset";
        Directory.CreateDirectory(directory);

        UniversalRendererData renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(
            rendererPath);
        if (renderer == null)
        {
            renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
            AssetDatabase.CreateAsset(renderer, rendererPath);
        }
        ResourceReloader.ReloadAllNullIn(
            renderer,
            UniversalRenderPipelineAsset.packagePath);
        EditorUtility.SetDirty(renderer);
        UniversalRenderPipelineAsset pipeline =
            AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(pipelinePath);
        if (pipeline == null)
        {
            pipeline = UniversalRenderPipelineAsset.Create(renderer);
            AssetDatabase.CreateAsset(pipeline, pipelinePath);
        }
        ResourceReloader.ReloadAllNullIn(
            pipeline,
            UniversalRenderPipelineAsset.packagePath);
        EditorUtility.SetDirty(pipeline);
        GraphicsSettings.defaultRenderPipeline = pipeline;
        QualitySettings.renderPipeline = pipeline;
        AssetDatabase.SaveAssets();
        return pipelinePath;
    }

    private static GameObject LoadPrefab(string path, string role, SceneReport report)
    {
        GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
        if (prefab == null)
            throw new FileNotFoundException("Configured " + role + " prefab was not found", path);
        report.usedAssetPaths.Add(path);
        return prefab;
    }

    private static Transform[] CreateSpawnPoints(Transform parent, VectorSpec[] values)
    {
        VectorSpec[] specs = values != null && values.Length >= 3
            ? values
            : new[]
            {
                new VectorSpec { x = -10f, z = 16f },
                new VectorSpec { x = 0f, z = 20f },
                new VectorSpec { x = 10f, z = 16f },
            };
        var result = new Transform[specs.Length];
        for (int index = 0; index < specs.Length; index++)
        {
            GameObject point = new GameObject("EnemySpawn_" + index);
            point.transform.SetParent(parent, false);
            point.transform.localPosition = specs[index].Value;
            result[index] = point.transform;
        }
        return result;
    }

    private static Type FindType(string fullName)
    {
        if (string.IsNullOrEmpty(fullName)) throw new ArgumentException("Component type is required");
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            Type type = assembly.GetType(fullName, false);
            if (type != null && typeof(Component).IsAssignableFrom(type)) return type;
        }
        throw new TypeLoadException("Unity component type was not found: " + fullName);
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
        return args.TryGetValue(key, out string value) && !string.IsNullOrEmpty(value) ? value : fallback;
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
        Debug.Log("[ComposeScene] report " + json);
    }
}
