/// <summary>
/// Editor-only script that sets up an ArenaFighter scene and launches Play mode.
/// Invoked via `Unity -batchmode -executeMethod ArenaFighterLauncher.Launch`.
/// </summary>
using UnityEditor;
using UnityEngine;
using ArenaFighterExample;

public static class ArenaFighterLauncher
{
    public static void Launch()
    {
        // 1. Create a new scene with default game objects (camera + light)
        var scene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
            UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects,
            UnityEditor.SceneManagement.NewSceneMode.Single);

        // 2. Create a GameManager GameObject with ArenaFighterGameMode
        var gameManager = new GameObject("GameManager");
        var gameMode = gameManager.AddComponent<ArenaFighterGameMode>();

        // 3. Position the camera to view the fight
        var cameraObj = GameObject.Find("Main Camera");
        if (cameraObj == null)
        {
            cameraObj = new GameObject("Main Camera");
            cameraObj.AddComponent<Camera>();
        }
        cameraObj.transform.position = new Vector3(0f, 8f, -10f);
        cameraObj.transform.rotation = Quaternion.Euler(45f, 0f, 0f);

        // 4. Create a ground plane
        var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Arena";
        ground.transform.localScale = new Vector3(3f, 1f, 3f);
        var renderer = ground.GetComponent<MeshRenderer>();
        if (renderer != null)
        {
            var mat = new Material(Shader.Find("Standard"));
            mat.color = new Color(0.3f, 0.3f, 0.35f);
            renderer.sharedMaterial = mat;
        }

        // 5. Save the scene
        string scenePath = "Assets/Scenes/ArenaFighter.unity";
        System.IO.Directory.CreateDirectory("Assets/Scenes");
        UnityEditor.SceneManagement.EditorSceneManager.SaveScene(scene, scenePath);

        // 6. Ensure spawn points exist (Awake may not run in batchmode)
        gameMode.SetupArena();

        // 7. Setup the fight (spawns player + AI opponent at spawn points)
        gameMode.Setup();

        Debug.Log("[ArenaFighterLauncher] Scene created successfully.");
        Debug.Log("[ArenaFighterLauncher] Player HP: " + gameMode.Player.MaxHealth);
        Debug.Log("[ArenaFighterLauncher] Opponent HP: " + gameMode.Opponent.MaxHealth);
        Debug.Log("[ArenaFighterLauncher] Enter Play mode to start the fight.");

        if (Application.isBatchMode)
        {
            EditorApplication.Exit(0);
        }
    }
}
