# Unity3D Agent API Reference

Status: implemented `UnityClient` API version `v1`.

Validated engine baseline: Unity 2022.3.62f3c1. Unity 6000.5 remains
unverified in this repository checkout.

This file is a compact index of implemented public capabilities. It lists
public names and their functions only. Read the current source when exact
parameters or result payload fields are required.

## Hard API Boundary

The only supported Python entry point is:

```text
from engine_adapters.unity3d import UnityClient
```

Agents, generated code, Pipeline code, and platform Serving code must not:

- import `engine_adapters.unity3d._internal`;
- import namespace client implementation classes directly;
- call transports, services, dispatchers, registries, or script builders;
- execute arbitrary Unity C# editor scripts through private transports;
- modify the adapter-owned `A3GameRuntime` framework;
- reference `A3GameRuntime` internal members;
- depend on optional ArenaFighter, FPS, or Racing example assemblies;
- construct generated-output paths manually.

Generated gameplay belongs in a separate project-local assembly (`.asmdef`).

## Execution Authority

The game-generation Agent generates engine-native test source. The Agent MUST
NOT invoke `unity.testing.*` or declare benchmark success.

Engine execution and evaluation code owns builds, Unity Test Framework
execution, runtime evidence, and benchmark results. A zero process return code
alone is not success; NUnit XML reports must contain matching passing tests.

## Result Contract

Public operations return JSON-serializable result dictionaries using these
stable top-level fields:

- `ok` - whether the operation completed successfully;
- `operation` - stable operation identifier;
- `artifacts` - produced or retained artifact descriptors;
- `diagnostics` - structured diagnostic records;
- `warnings` - non-fatal problems;
- `errors` - fatal problems;
- `payload` - operation-specific result data.

## Client

- `UnityClient` - Creates the public Unity environment client and its namespace
  clients.
- `unity.api_version` - Reports the active public UnityClient API version.
- `unity.get_environment_info` - Reports configured project, Engine, transport,
  and runtime environment information.

## One-Client Generated Game Lifecycle

Unity has its own native implementation behind the same Agent-facing shape as
UE5. The supported workflow is one long-lived `UnityClient` instance; do not
mix direct Unity CLI calls with client calls or construct a second asset/session
registry. For a complete generated game, `UnityClient.generate_game()` is the
normal one-call path:

1. Generate and finalize mechanic and UI task artifacts through the existing
   code-generation skills.
2. Construct one `UnityClient` for the generated project and call
   `unity.generate_game(...)`. The client resolves the canonical descriptors,
   writes `Library/A3GameForge/jobs/generate_game.json`, and submits one
   `GenerateGame.RunFromCLI` job to Unity. Inside that one Editor lifecycle,
   Unity copies the finalized mechanic/UI assemblies, imports the avatars,
   weapons, motions, scenes/packages through `AssetDatabase`, composes the
   supplied scene specification, refreshes and compiles scripts, invokes
   `BuildPipeline`, and optionally enters Play Mode. An already-open GUI Editor
   is reused; otherwise the transport starts one batchmode Editor.
3. For incremental work, the same client exposes `unity.assets.*`,
   `unity.world.build`, `unity.plugin.install`, and
   `unity.world.compose_scene`; these use the same Unity-native Editor methods.
4. Execution/evaluation code calls `unity.testing.run_automation_tests` and
   requires a fresh passing NUnit report. A zero Editor exit code without a
   report is failure.
5. Call `unity.build.project`, then launch its concrete native artifact with
   `unity.runtime.launch_player`; stop it with the same client's
   `unity.runtime.stop_player`.
6. For an interactive run, use that same client's
   `unity.runtime.sessions.join`, `apply_input`, `snapshot`, `leave`, and
   `clear_entity`. The client sends UDP commands to the generated project's
   `A3GameRuntimeInputReceiver`; a queued UDP datagram is not proof that Unity
   processed it. Confirm processing through `snapshot`/runtime evidence.

The task descriptors in steps 3 and 4 preserve the canonical
`game_id/run_id/task_kind/task_id` trace. Examples under the adapter are
read-only generation references and are never copied as the generated game.

## Project

- `unity.project.get_info` - Reports the configured Unity project and Engine
  paths.
- `unity.project.synchronize_packages` - Merges the adapter-required Unity
  packages and built-in engine modules into an existing project manifest.
- `unity.project.create` - Creates a minimal Unity host project with
  `ProjectSettings`, `Packages/manifest.json`, content folders, and a real
  `A3GameBootstrap` MonoBehaviour.
- `unity.project.validate` - Checks project configuration, ProjectSettings,
  Packages manifest, and required asset folder structure.

## Assets

- `unity.assets.import_asset` - Imports a registered task artifact using its
  declared asset type.
- `unity.assets.import_avatar` - Imports a registered character or avatar
  artifact.
- `unity.assets.import_motion` - Imports registered animation data against an
  explicit target skeleton.
- `unity.assets.import_scene` - Imports a registered Scene artifact.
- `unity.assets.import_prop` - Imports a registered prop or generic mesh artifact.
- `unity.assets.import_weapon` - Imports a registered weapon mesh artifact.
- `unity.assets.import_material` - Imports a registered material artifact.
- `unity.assets.import_texture` - Imports a registered texture artifact.
- `unity.assets.import_effect` - Imports a registered effect artifact.
- `unity.assets.validate` - Validates a registered source artifact without
  requiring a live Unity connection when possible.
- `unity.assets.resolve_source` - Resolves a repository task identity to its
  registered source artifact.
- `unity.assets.list` - Lists assets in the configured Unity project through
  the Editor subprocess transport.
- `unity.assets.list_registered` - Lists artifacts recorded in the adapter
  registry.
- `unity.assets.get_metadata` - Reads metadata for one registered artifact.

Public asset methods consume repository task identities. They do not accept
arbitrary generated-output filesystem paths.

A source descriptor has this shape:

```json
{
  "game_id": "gameB_fps_test",
  "run_id": "unity_e2e_20260811_101356",
  "task_kind": "3d_object",
  "task_id": "rifle",
  "artifact_key": "model_path"
}
```

`task_kind` can be inferred from a known asset type. `artifact_key` can be
omitted only when `meta.json` contains exactly one non-empty `*_path` field.
Use the key naming the generated artifact, such as `model_path`; provenance
fields such as `source_path` are not Unity import inputs. Resolved artifacts
must exist inside the canonical task output directory.

### Import Lifecycle

`scripts/unity/import_asset.sh` and `scripts/unity/import_asset.cmd` are thin
CLI wrappers around the same public `UnityClient`; they are not a second asset
API. `--dry-run` resolves and validates the canonical source without importing
it. A non-dry-run import invokes the client-owned Editor transport. The
transport installs the required Editor method in the generated project and
runs it with the project root as cwd, so every `Assets/...` path is resolved by
Unity itself. The client owns only processes it launched; use the same client
instance for `stop_editor`/`stop_player`.

For a complete generated asset set, use `unity.assets.import_batch([...])`.
The descriptors are resolved from canonical output paths first, then ordered
as avatars/meshes, motions, and scenes. Motions automatically use the batch's
first avatar prefab when no `skeleton` is supplied. The client invokes
`ImportBatch.RunFromCLI` once, so Unity imports and refreshes all assets in one
Editor process. The individual import methods remain available for incremental
updates.

### FBX/GLB material contract

`ImportGeneratedAvatar` and `ImportGeneratedMesh` run the same generic
post-import material pass for skeletal and static assets. When the source
contains embedded texture bytes or material descriptions, the Editor:

1. copies the source into `Assets/Imported/...`;
2. extracts embedded textures to `Assets/Generated/Textures/<asset_name>/`;
3. creates project-local URP/Lit (or Standard) materials under
   `Assets/Generated/Materials/<asset_name>/`;
4. binds base-color/diffuse, normal, metallic/roughness, and occlusion maps
   when present; and
5. remaps the FBX material slots to those project-local materials before saving
   the generated prefab.

Avatar and mesh reports include `extractedTextures`, `generatedMaterials`,
`remappedMaterials`, `boundTextures`, `materialDetails`, and `warnings`.
Successful file copy with zero extracted or bound textures is reported as an
untextured import; it is not silently considered a complete visual import.
Sources that contain no embedded texture payload can still be valid, but the
warning remains available to the Agent for traceability.

The environment importer preserves the `.unitypackage` asset paths and GUID
references. It discovers the package root from pathname records, imports the
scene, prefabs, materials, textures, shader graphs, and package-local collider
data in one AssetDatabase operation, and audits the selected scene in its
report. It does not replace a package scene with a generated primitive floor.

Material repair is part of the reusable adapter Editor scripts installed by
`UnityClient`; a project-specific `RepairFPSArenaMaterials.cs` is not a
dependency. A project generated before this contract existed can have
`materialImportMode: 2` in its `.fbx.meta` while still lacking generated
textures/materials. Re-run `UnityClient.generate_game()` (or
`unity.assets.import_batch`) with `replace_existing=True` so the current
importer extracts and remaps the materials in that project. Do not reference
`test_samples/` or `asset/` directly at runtime as a substitute.

## Animation

- `unity.animation.import_motion` - Imports motion through the Animation
  namespace.
- `unity.animation.resolve_skeleton` - Resolves the skeleton associated with a
  registered avatar or imported asset.
- `unity.animation.validate_compatibility` - Checks whether motion and skeleton
  artifacts are compatible.

## Bindings

- `unity.bindings.bind_pbr_material` - Creates or updates a PBR material binding
  for an imported asset.

## World

- `unity.world.compose_scene` - Composes and saves a Unity scene from a
  structured specification of imported prefab/component references.
- `unity.world.build` - Imports a registered Scene artifact through the Unity
  Editor, registers the resulting environment artifact, creates and validates
  a World draft, and publishes a World package by default. Set
  `options={"publish": False}` to keep only the validated draft.
- `unity.world.create_draft` - Creates a persistent editable World draft.
- `unity.world.validate_draft` - Validates a World draft and its referenced
  artifacts.
- `unity.world.publish_draft` - Publishes a validated draft as a registered World
  package.
- `unity.world.list_packages` - Lists registered World packages.

World operations preserve native Unity scenes when a task supplies a native
scene asset and record the selected scene in the shared artifact registry.
`.unitypackage` files are dispatched to the package importer,
their package root is discovered from pathname records, and the selected scene
path is returned in the result. A `.unity` file or native scene directory is
copied with its `.meta` files so scene/material/texture GUID references survive
the import.

`unity.world.compose_scene` accepts the legacy FPS example fields and a generic
`objects` form. The generic form is the normal generated-game contract:

```json
{
  "output_scene": "Assets/Scenes/GeneratedGame.unity",
  "base_scene": "Assets/Imported/Scenes/Environment.unity",
  "create_ground": false,
  "objects": [
    {
      "name": "GameRuntime",
      "prefab_path": "",
      "parent": "",
      "position": {"x": 0, "y": 0, "z": 0},
      "rotation": {"x": 0, "y": 0, "z": 0},
      "scale": {"x": 1, "y": 1, "z": 1},
      "active": true,
      "components": [
        {
          "type": "GeneratedMechanic.GameRuntime",
          "fields": [
            {"name": "hud", "kind": "object", "object_name": "HUD"},
            {"name": "weapon", "kind": "asset", "asset_path": "Assets/Imported/Weapons/Gun.prefab"}
          ]
        }
      ]
    }
  ]
}
```

Supported field kinds are `asset`, `object`, `vector3`, `bool`, `int`, `float`,
`enum`, and `string`. Object references may target a `GameObject`, `Transform`,
or a component on any declared object. Scene object names must be unique.

## Plugin

- `unity.plugin.install` - Installs a registered generated Gameplay assembly
  into a project's `Assets/` directory.
- `unity.plugin.install_framework` - Installs the adapter-owned
  `A3GameRuntime` Runtime Framework.
- `unity.plugin.list` - Lists installed project assemblies.

Generated Gameplay assemblies may depend only on `A3GameRuntime` public API.

## Build

- `unity.build.project` - Builds a Unity project target and returns structured
  command and diagnostic evidence.

With no explicit target, `unity.build.project` selects the current host's
native standalone target. With no configured scene, it creates a minimal
project-local bootstrap scene. `clean=True` removes only the selected build
output before invoking `BuildPipeline.BuildPlayer`.

## Testing

- `unity.testing.run_automation_tests` - Runs Unity Test Framework tests,
  parses a fresh NUnit XML report, and returns authoritative matched, passed,
  and failed counts.

The game-generation Agent must not invoke this namespace.

The Unity Test Framework command intentionally omits `-quit`; Unity exits after
the test run. Process pipes are closed and Unity writes to
`TestResults/unity-tests.log`, preventing package/compiler child processes from
holding Python pipes open.

## Runtime

- `unity.runtime.launch_editor` - Launches the configured Unity Editor for the
  project and optional scene.
- `unity.runtime.stop_editor` - Stops Editor processes started by the same
  runtime client.
- `unity.runtime.launch_player` - Launches a concrete native player executable
  produced by `unity.build.project`.
- `unity.runtime.stop_player` - Stops native player processes started by the
  same runtime client.

Process ownership is in-memory. A `stop_editor` or `stop_player` call must use
the same `UnityClient` instance that launched the process. The one-shot
`scripts/unity/run.sh` and `.cmd` wrappers launch an Editor and then exit, so
they do not provide a later CLI stop operation.

## Runtime Sessions

The browser-serving Unity path is separate from native Editor/Player runtime
sessions. A Unity WebGL build is itself the browser runtime: `stream_url` points
to an HTTP-served `index.html`, not to an Unreal Pixel Streaming/WebRTC page.
The WebGL session must report `runtime_kind="unity_webgl"` and
`input_transport="browser_canvas"`. The iframe receives keyboard and pointer
events directly in Unity's canvas; the browser API may acknowledge and record
input, but must not claim that a native UDP receiver processed it. Native
Editor/Player sessions continue to use the UDP contract below.

The browser backend must first verify `Builds/WebGL/index.html` and a successful
HTTP GET before returning a ready stream. If `build.project(target="WebGL")`
is blocked by Unity LicensingClient before compilation, browser validation is
`BLOCKED`; a desktop GUI Play Mode run does not prove WebGL rendering.

- `unity.runtime.sessions.join` - Creates or updates a generic participant,
  controller, entity, and control-binding session.
- `unity.runtime.sessions.leave` - Marks a participant/controller offline
  without destroying its persistent entity.
- `unity.runtime.sessions.heartbeat` - Refreshes participant liveness.
- `unity.runtime.sessions.apply_input` - Applies normalized control input to a
  bound runtime entity.
- `unity.runtime.sessions.snapshot` - Returns the current generic runtime session
  state.
- `unity.runtime.sessions.reset_world` - Requests a generic runtime World reset.
- `unity.runtime.sessions.clear_entity` - Removes an entity and its associated
  bindings from session state.

Runtime sessions are game-neutral and do not define Fighter, FPS, or Racing
commands.

### Input Fields

Normalized input state fields are identical to UE5:

- `move_x` - strafe input (-1.0 to 1.0)
- `move_y` - forward/back input (-1.0 to 1.0)
- `run` - whether the run modifier is active
- `jump` - whether the jump action is triggered
- `yaw` - yaw rotation delta
- `pitch` - pitch rotation delta
- `seq` - monotonic sequence number per session

Input is delivered via UDP to the `A3GameRuntimeInputReceiver` C# component
(port 30030 by default). The receiver applies only inputs with `seq` greater
than the last applied; duplicate or out-of-order packets are silently dropped.
The bridge keeps avatar, idle-motion, and movement-motion `Assets/...` paths at
the top level of `sync_session` so Unity-side factories can instantiate the
imported prefab and bind its clips. It also accepts the legacy shape where
those fields exist only in `parameters`. Imported avatar and motion records
carry a separate `runtime.path` under `Assets/Resources/...`; session joins
prefer that Player-loadable path while retaining the editor-facing
`backend_path`. The opaque `parameters` object remains available for
game-specific configuration.

## Reflection

- `unity.reflection.inspect_artifact` - Inspects a registered imported artifact
  through C# reflection and returns structured metadata.

## Observation

- `unity.observe.check_status` - Reports editor transport, project, runtime,
  and observation readiness.

## A3GameRuntime Public C# Contract

Generated Gameplay assemblies may reference only the public API under:

```text
A3GameRuntime/Runtime/
```

### Enums

- `A3GameControlMode` - Identifies the generic control mode assigned to an
  entity.
- `A3GameLocomotionState` - Represents generic locomotion state for runtime
  snapshots.

### Data Types

- `A3GameRuntimeInputState` - Carries normalized movement, look, action, and
  input timing state.
- `A3GameEntitySpawnRequest` - Describes a generic entity spawn request.
- `A3GameParticipantInfo` - Describes one runtime participant.
- `A3GameControllerState` - Describes one generic controller.
- `A3GameControlBinding` - Connects a participant, controller, and entity.
- `A3GameEntitySnapshot` - Reports observable generic entity state.

### Interfaces

- `IA3GameControllableEntity` - Contract implemented by game-owned
  controllable entities.
- `IA3GameEntityFactory` - Contract implemented by game-owned entity
  factories.
- `IA3GameRuntimeMessageHandler` - Contract for game-owned runtime message
  handling.

### Components

- `A3GameIdentityComponent` - Stores stable runtime identity on a game-owned
  GameObject.
- `A3GameRuntimeEntityComponent` - Connects a game-owned GameObject to runtime
  entity state and control. Its `RuntimeInput` event dispatches accepted
  normalized input to concrete gameplay without implementing movement itself.

### Subsystems

- `A3GameRuntimeSubsystem` - Registers game-owned factories and coordinates
  generic runtime entity creation.
- `A3GameWorldSessionSubsystem` - Owns generic participant, controller,
  entity, binding, input, and snapshot session state.
- `A3GameRuntimeInputReceiver` - Receives UDP input datagrams and forwards
  them to the runtime subsystem (port 30030).

## Framework Boundaries

`A3GameRuntime` provides runtime contracts and coordination components only.
It does not provide a concrete player character/controller, movement or
physics implementation, weapon, vehicle, combat rule, or game-specific input
mapping.

Generated projects own concrete gameplay implementation. Optional
ArenaFighterExample, FPSExample, and RacingExample assemblies are read-only
references and are not dependencies or success criteria.

## Transport

Unity does not have Unreal's Python Remote Execution or HTTP Remote Control.
The `UnityClient` uses a subprocess transport. Every Editor invocation sets
the subprocess working directory to the generated Unity project root. This is
required because Unity Editor scripts use project-relative paths such as
`Assets/Imported/Weapons`; without that cwd contract, a relative file operation
could write outside the project and AssetDatabase would not see the import:

1. Copies the required bundled C# Editor script into the project's
   `Assets/Editor/` folder when needed
2. Writes operation arguments to a temporary JSON job file
3. Invokes `Unity -batchmode -quit -projectPath <proj> -executeMethod
   <Class.Method> --job <job.json> --report <report.json>`
4. The C# script writes a JSON report to a temporary file
5. The Python transport reads the JSON report and returns it

### Unity licensing prerequisite

Unity licensing is an external host prerequisite, not an AAAGameForge
operation. Before invoking a mutating client method, the selected Editor must
be installed and activated through the matching Unity Hub/Tuanjie Hub account,
or an already-open licensed Editor must be available. `UnityClient` does not
discover credentials, activate seats, or replace the Hub licensing daemon.

The direct batch transport deliberately does not force `-licensingIpc`: Unity
and its Hub choose the correct local LicensingClient channel. If the host has
conflicting Hub daemons or no activation, Unity can exit before loading the
project (commonly exit code 199). The transport returns
`blocked=true`, `blocked_stage="licensing"`, `license_status`, and the log
tail in that case, so callers fail fast with the external prerequisite rather
than claiming that import, compilation, or build succeeded.

The files under `scripts/unity/` are compatibility launchers only. They do not
implement import, material repair, scene loading, compilation, or runtime
behavior. `scripts/unity/import_asset.sh import-batch ...` and the Windows
equivalent dispatch the top-level `import-batch` public client command. Use
`generate-game` for the complete pipeline so one Editor session owns plugin
installation, asset import, material remapping, scene composition, compile,
build, and optional Play Mode.

### Runtime Input Transport

For runtime sessions, a `RuntimeUDPBridge` sends JSON datagrams to the
`A3GameRuntimeInputReceiver` C# component (UDP port 30030), mirroring UE5's
UDP bridge to `A3GameRuntimeInputPort` (port 30020).

## Coordinate System

glTF and Unity are Y-up and use metres, but their handedness conventions
differ. Unity's model importer performs the format conversion; adapter or
gameplay code should not add a second blanket axis conversion. FBX authoring
axes and units can vary, so imported orientation, scale, rig, and weapon
forward direction still require inspection or importer configuration.

# Unity API Context

For smoke, fire, explosion, dust, and particle lifecycle work, use the
[`create-vfx-effects`](create-vfx-effects/SKILL.md) skill and
`engine_adapters/unity3d/vfx/Runtime/A3Game_VFX.cs`.

Prefer an existing reviewed particle or VFX Graph prefab through `SpawnPrefab`.
The named ParticleSystem functions are no-asset fallbacks. Their positions use
Unity world-space meters.

The procedural style fallbacks are `SpawnInkSmoke`, `SpawnFrostFire`, and
`SpawnCyberFire`. Prefer authored prefabs when available; the style functions are
layered fallbacks and still require visual approval.

## Import Generated Meshes

Use the host launcher for generated GLB, FBX, or OBJ files:

```bash
python scripts/import_generated_asset.py --engine unity \
    --src <model> --unity-project <project>
```

The launcher installs
`engine_adapters/unity3d/import_generated/ImportGeneratedMesh.cs` under the
project's `Assets/Editor/` directory and invokes `ImportGeneratedMesh.RunFromCLI`.
Use `--usage asset` for ordinary meshes, `vfx_standalone` for a single effect
mesh, and `vfx_particle` for meshes instanced by a particle system.

Treat the JSON import report as the result contract. Check `ok`, `assetPath`,
`prefabPath`, triangle and material counts, bound textures, bounds, and warnings
before referencing the prefab. GLB import requires `com.unity.cloud.gltfast`;
the full project setup is in `scripts/installing/engine_import_setup.md`.
