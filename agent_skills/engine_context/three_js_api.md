# three.js Agent API Reference

Status: implemented `ThreeClient` API version `v1`.

Validated engine baseline: three.js r185 (`three@0.185.0`), Node 20,
Vite 6.

This file is a compact index of implemented public capabilities. It lists
public names and their functions only. Read the current source when exact
parameters or result payload fields are required.

## Hard API Boundary

The only supported Python entry point is:

```text
from engine_adapters.three_js import ThreeClient
```

The only supported JavaScript entry point for generated gameplay is:

```text
import { ... } from '@a3game/playable';
```

Agents, generated code, Pipeline code, and platform Serving code must not:

- import `engine_adapters.three_js._internal`;
- import namespace client implementation classes directly;
- import any `_internal` subpackage of a namespace;
- call transports, services, registries, resolvers, or inspectors;
- run arbitrary Node or npm commands through private transports;
- modify the adapter-owned `A3GamePlayable` framework;
- deep-import `@a3game/playable/src/...` paths;
- depend on optional Arena Fighter, FPS, or Racing example packages;
- hard-code asset URLs, `dist/` paths, or `public/` paths;
- construct generated-output paths manually.

Generated gameplay belongs in a separate project-local Gameplay Package
under `packages/`.

## Execution Authority

The game-generation Agent generates engine-native test source. The Agent
MUST NOT invoke `three.testing.*` or declare benchmark success.

Engine execution and evaluation code owns bundle builds, test execution,
runtime evidence, and benchmark results. A zero process return code alone
is not success; the parsed test report must contain matching passing
tests.

## Result Contract

Public operations return JSON-serializable result dictionaries using
these stable top-level fields:

- `ok` - whether the operation completed successfully;
- `operation` - stable operation identifier;
- `artifacts` - produced or retained artifact paths;
- `diagnostics` - structured diagnostic records;
- `warnings` - non-fatal problems;
- `errors` - fatal problems;
- `payload` - operation-specific result data.

## Client

- `ThreeClient` - Creates the public three.js environment client and its
  namespace clients.
- `three.api_version` - Reports the active public ThreeClient API version.
- `three.get_environment_info` - Reports configured project, three.js
  baseline, dev server, runtime channel, and registry information.

Constructor arguments: `project_path`, `three_root`, `api_version`, and
keyword-only `host`, `port`, `runtime_host`, `runtime_port`,
`package_manager`, `runtime_transport`, `node_root`. Every argument also
resolves from `A3GAME_THREE_*` environment variables.

## Project

- `three.project.get_info` - Reports the configured project and three.js
  baseline paths.
- `three.project.create` - Creates a minimal Vite + three.js host project
  without concrete gameplay defaults.
- `three.project.install_dependencies` - Installs Node dependencies with
  the configured package manager.
- `three.project.validate` - Checks project configuration, descriptor,
  entry document, static root, and installed dependencies.

`project.create` writes `package.json`, `vite.config.js`, `index.html`,
`src/main.js`, the `public/assets/imported/*` roots, `packages/`,
`tests/`, and the `.a3game-three.json` descriptor. It installs no
gameplay.

## Assets

- `three.assets.import_asset` - Stages a registered task artifact using
  its declared asset type.
- `three.assets.import_avatar` - Stages a registered character or avatar
  artifact.
- `three.assets.import_motion` - Stages registered animation data,
  optionally against a target skeleton artifact.
- `three.assets.import_scene` - Stages a registered Scene artifact.
- `three.assets.import_prop` - Stages a registered prop or generic mesh
  artifact.
- `three.assets.import_weapon` - Stages a registered weapon mesh
  artifact.
- `three.assets.import_material` - Stages a registered material
  artifact.
- `three.assets.import_texture` - Stages a registered texture artifact.
- `three.assets.import_effect` - Stages a registered Effect package or
  native Effect content.
- `three.assets.import_audio` - Stages a registered audio artifact.
- `three.assets.validate` - Validates a registered source artifact
  without staging it and without a Node process.
- `three.assets.resolve_source` - Resolves a repository task identity to
  its registered source artifact.
- `three.assets.list` - Lists staged asset files under the project static
  root.
- `three.assets.list_registered` - Lists artifacts recorded in the
  adapter registry.
- `three.assets.get_metadata` - Reads metadata for one registered
  artifact.
- `three.assets.write_manifest` - Rewrites the runtime asset manifest
  from the registry.

Public asset methods consume repository task identities. They do not
accept arbitrary generated-output filesystem paths.

### Import Lifecycle

The web has no engine-side import step: a `.glb` file is already the
runtime format. `import_asset` therefore stages the file into
`public/<destination>/`, copies any `.gltf` sidecar buffers and images,
records an artifact, and rewrites the manifest.

`scripts/three/import_asset` is a lifecycle wrapper around the same
public `ThreeClient`; it is not a second or faster asset API.

Asset and World operations need no live browser. Execution code should
reuse one `ThreeClient` for a task batch.

### Asset Manifest

Every import rewrites `public/assets/manifest.json`. This file is the
only supported way for generated gameplay to find an asset:

```json
{
  "manifest_version": 1, "api_version": "v1", "backend": "web",
  "engine": "three_js", "engine_version": "0.185.0",
  "assets": {
    "<artifact_id>": {
      "artifact_id": "...", "asset_id": "hero", "package_id": "hero",
      "type": "avatar", "category": "", "representation": "gltf_binary",
      "class": "SkinnedMesh", "url": "/assets/imported/avatars/hero.glb",
      "capabilities": {
        "renderable": true, "spawnable": true, "collidable": false,
        "playable": false, "animated": true, "skinned": true
      },
      "animations": ["idle", "walk"],
      "bounds": { "min": [], "max": [], "size": [], "center": [] }
    }
  }
}
```

### Default Destinations

`avatar` → `assets/imported/avatars`, `motion` → `.../motions`,
`scene` → `.../scenes`, `environment` → `.../environments`,
`effect` → `.../effects`, `material` → `.../materials`,
`texture` → `.../textures`, `prop` and `static_mesh` → `.../props`,
`weapon` → `.../weapons`, `audio` → `.../audio`.

### Runtime Formats

`glb`/`gltf` are the only supported mesh formats for shipped content;
`png`, `jpeg`, `webp`, `ktx2`, `basis`, `hdr` for images; `mp3`, `ogg`,
`wav` for audio. `fbx`, `obj`, `stl`, `ply`, and `usdz` load but validate
with a warning and should be converted. Draco and meshopt compression are
supported when the runtime configures the matching decoder.

## Animation

- `three.animation.import_motion` - Stages motion through the Animation
  namespace.
- `three.animation.resolve_skeleton` - Reports the skinned hierarchy
  carried by a registered artifact.
- `three.animation.validate_compatibility` - Checks whether motion clips
  can drive a target avatar skeleton and whether retargeting is required.

## Bindings

- `three.bindings.bind_pbr_material` - Stages a PBR texture set and
  writes a runtime material binding for registered mesh artifacts.

Bindings are written to `public/assets/bindings/<asset_id>.json` and
applied at runtime by `A3GameAssetLibrary.applyMaterialBinding`. Texture
slots are inferred from file names (`_basecolor`, `_normal`,
`_roughness`, `_metallic`, `_ao`, `_emissive`, `_alpha`, `_height`).

## World

- `three.world.build` - Builds or imports a World from a registered Scene
  artifact.
- `three.world.create_draft` - Creates a persistent editable World draft.
- `three.world.validate_draft` - Validates a World draft and its
  referenced artifacts.
- `three.world.publish_draft` - Publishes a validated draft as a
  registered World package and writes its runtime scene graph.
- `three.world.list_packages` - Lists registered World packages.
- `three.world.get_scene_graph` - Returns the runtime scene graph
  document for one draft without publishing it.

Publishing writes `public/assets/worlds/<world_id>.json`. That document,
not a hand-built scene, is what `A3GameSceneLoader` consumes.

### World Spec Schema

Coordinates are right-handed, Y-up, metres; rotations are radians.

- `world_id`, `name`, `project_id`, `metadata`;
- `environment` - `background`, `environment_artifact_id`,
  `background_intensity`, `tone_mapping`, `tone_mapping_exposure`,
  `shadows`, `fog` (`type`/`color`/`near`/`far`/`density`), `ground`;
- `camera` - `type`, `fov`, `near`, `far`, `position`, `target`,
  `controls`;
- `lights[]` - `light_id`, `type`, `color`, `intensity`, `position`,
  `target`, `cast_shadow`, plus type-specific `options`;
- `entities[]` - `entity_id`, `role`, `artifact_id`, `category`,
  `collision`, `cast_shadow`, `receive_shadow`, `transform`
  (`position`/`rotation`/`scale`), `behaviors[]`, `parameters`;
- `spawn_points[]` - `name`, `position`, `rotation`.

Supported light types: `AmbientLight`, `HemisphereLight`,
`DirectionalLight`, `PointLight`, `SpotLight`, `RectAreaLight`.
Supported camera controls: `none`, `OrbitControls`,
`PointerLockControls`, `MapControls`, `FlyControls`.
Supported entity roles: `environment`, `player_start`, `prop`, `npc`,
`pickup`, `trigger`, `vehicle`, `weapon`, `effect`.
Supported behavior types: `animation`, `spin`, `orbit`, `float`, `path`,
`audio`.

## Plugin

- `three.plugin.install` - Installs a registered generated Gameplay
  Package into a project and synchronizes declared framework
  dependencies.
- `three.plugin.install_framework` - Installs the adapter-owned
  `A3GamePlayable` Runtime Framework as `@a3game/playable`.
- `three.plugin.list` - Lists installed project packages.

Installation copies the package into `packages/<name>`, adds a
`file:./packages/<name>` dependency, and ensures a `packages/*` workspace
entry. Generated Gameplay Packages may depend only on the
`@a3game/playable` public export surface. Declaring `@a3game/playable`
makes `plugin.install` install the framework automatically.

## Build

- `three.build.project` - Builds the project's web bundle and returns
  structured command and diagnostic evidence.

## Testing

- `three.testing.run_automation_tests` - Runs generated web tests with
  `vitest` or `playwright`, parses a fresh report, and returns
  authoritative matched, passed, failed, and skipped counts.

The runner deletes any prior report, refuses to score a stale report,
and fails when the report matches zero tests. The game-generation Agent
must not invoke this namespace.

## Runtime

- `three.runtime.launch_dev_server` - Starts the configured Vite dev
  server and waits until it answers.
- `three.runtime.stop_dev_server` - Stops dev server processes started by
  the same runtime client.
- `three.runtime.preview_bundle` - Serves the built bundle from `dist/`
  for evidence capture.

## Runtime Sessions

- `three.runtime.sessions.join` - Creates or updates a generic
  participant, controller, entity, and control-binding session.
- `three.runtime.sessions.leave` - Removes a participant from the runtime
  session.
- `three.runtime.sessions.heartbeat` - Refreshes participant liveness.
- `three.runtime.sessions.apply_input` - Applies normalized control input
  to a bound runtime entity.
- `three.runtime.sessions.snapshot` - Returns the current generic runtime
  session state.
- `three.runtime.sessions.reset_world` - Requests a generic runtime World
  reset.
- `three.runtime.sessions.clear_entity` - Removes an entity and its
  associated bindings from session state.

Runtime sessions are game-neutral and do not define Fighter, FPS, or
Racing commands. Each call also forwards a generic command to the browser
runtime control channel; the returned `runtime_delivery` field reports
whether delivery succeeded, so session bookkeeping stays usable when no
browser is attached.

## Reflection

- `three.reflection.inspect_artifact` - Inspects a registered staged
  artifact through glTF document reflection and returns structured
  metadata.
- `three.reflection.list_object_names` - Lists animation clip and
  material names carried by an artifact.

## Observation

- `three.observe.check_status` - Reports Node toolchain, package manager,
  project, dependency, framework, dev server, and runtime channel
  readiness.

## A3GamePlayable Public JavaScript Contract

Generated Gameplay Packages may import only from:

```text
@a3game/playable
```

### Enums

- `A3GameControlMode` - Identifies the generic control mode assigned to
  an entity: `EXCLUSIVE`, `PRIORITY`, `ASSISTED`, `OBSERVING`.
- `A3GameLocomotionState` - Represents generic locomotion state for
  runtime snapshots: `IDLE`, `WALK`, `RUN`, `JUMP`.
- `A3GameRuntimeCommand` - Names the generic runtime commands:
  `SYNC_SESSION`, `LEAVE_SESSION`, `APPLY_INPUT`, `WORLD_SNAPSHOT`,
  `RESET_WORLD`, `CLEAR_ENTITY`.

### Data Types

Factory functions normalize and clamp their input, so the same payload is
valid in Python, on the wire, and in the browser.

- `createRuntimeInputState` - Carries normalized movement, look, action,
  and input timing state (`moveX`, `moveY`, `run`, `jump`, `yaw`,
  `pitch`, `sequence`, `timestampSeconds`).
- `createEntitySpawnRequest` - Describes a generic entity spawn request.
- `createParticipantInfo` - Describes one runtime participant.
- `createControllerState` - Describes one generic controller.
- `createControlBinding` - Connects a participant, controller, and
  entity.
- `createEntitySnapshot` - Reports observable generic entity state.
- `createTransform` / `createVector3` - Serializable transform helpers.
- `locomotionStateFromInput` - Derives a locomotion state from one input
  frame.

### Interfaces

Each contract is an abstract base class plus a duck-type validator, so
generated gameplay may extend it or implement the methods on any object.

- `A3GameControllableEntity` - Contract implemented by game-owned
  controllable entities: `getRuntimeEntityId`, `setRuntimeEntityId`,
  `applyRuntimeInput`, `getRuntimeSnapshot`, optional `tick`, `dispose`.
- `A3GameEntityFactory` - Contract implemented by game-owned entity
  factories: `spawnRuntimeEntity(request, { host, assets, session })`.
- `A3GameRuntimeMessageHandler` - Contract for game-owned runtime message
  handling: `handleRuntimeMessage(messageType, payload)`.
- `isControllableEntity` / `assertControllableEntity`,
  `isEntityFactory` / `assertEntityFactory`,
  `isRuntimeMessageHandler` / `assertRuntimeMessageHandler`.

### Components

three.js has no component system, so components attach through
`object.userData.a3game`.

- `A3GameIdentityComponent` - Stores stable runtime identity on a
  game-owned `Object3D`; `attach`, `get`, `findInParents`,
  `setRuntimeIdentity`.
- `A3GameRuntimeEntityComponent` - Connects a game-owned `Object3D` to
  runtime entity state and control; `setRuntimeEntityId`,
  `applyRuntimeInput`, `onRuntimeInput`, `setMotionState`,
  `getRuntimeSnapshot`, `dispose`. Drops out-of-order input frames.

### Subsystems

- `A3GameRuntimeSubsystem` - Registers game-owned factories and
  coordinates generic runtime entity creation; `setEntityFactory`,
  `registerMessageHandler`, `unregisterMessageHandler`,
  `getSessionSubsystem`, `onWorldBeginPlay`, `deinitialize`,
  `spawnEntity`, `handleRuntimeCommand`, `dispatchExtensionMessage`.
- `A3GameWorldSessionSubsystem` - Owns generic participant, controller,
  entity, binding, input, and snapshot session state;
  `registerParticipant`, `markParticipantOffline`, `createController`,
  `registerEntity`, `getEntity`, `removeEntity`,
  `bindControllerToEntity`, `unbindController`, `syncSession`,
  `enqueueInputState`, `consumeLatestInputs`, `getWorldStateSnapshot`,
  `getSessionSnapshot`, `resetWorld`.

### Engine Scaffolding

Unreal supplies these natively; on the web the framework must own them.
They are game-neutral.

- `A3GameRuntimeHost` - Owns renderer, scene, camera, controls, and frame
  loop; `init`, `start`, `stop`, `tick`, `onTick`, `onResize`, `add`,
  `remove`, `getRoot`, `attachOrbitControls`, `attachPointerLockControls`,
  `detachControls`, `setEnvironment`, `setFog`, `raycastFromPointer`,
  `raycast`, `captureFrame`, `getStats`, `dispose`.
- `disposeObject3D` - Recursively disposes geometries, materials, and
  textures.
- `A3GameAssetLibrary` - Loads the asset manifest and resolves artifacts;
  `load`, `findEntry`, `requireEntry`, `listByType`, `loadArtifact`,
  `instantiate`, `applyMaterialBinding`, `dispose`.
- `A3GameSceneLoader` - Builds a scene from a published world scene
  graph; `loadWorld`, `buildWorld`, `getEntityObject`,
  `resolveSpawnTransform`, plus `collisionTargets` and `spawnPoints`.
- `A3GameInputRouter` - Converts keyboard, pointer, and gamepad events
  into normalized input frames; `enable`, `disable`, `reset`, `onAction`,
  `isActionHeld`, `sample`, `pipeToSession`. `DEFAULT_KEY_BINDINGS` maps
  WASD/arrows, Shift, and Space.
- `A3GameAnimationDirector` - Wraps `AnimationMixer`; `addClip`,
  `addClips`, `listClipNames`, `mapState`, `mapStates`, `play`,
  `playOnce`, `stopAll`, `update`, `attachToHost`, `getState`,
  `dispose`.
- `A3GameCollisionProbe` - Raycast ground, wall, and hitscan primitives;
  `setTargets`, `addTarget`, `sampleGround`, `resolveMove`,
  `stepCharacter`, `hitscan`.
- `A3GameHudLayer` - DOM overlay HUD; `addText`, `addBar`,
  `addCrosshair`, `setValue`, `setValues`, `setVisible`, `remove`,
  `getState`, `dispose`. Every widget writes `data-a3game-*` attributes
  so end-to-end tests assert HUD state without screenshots.
- `A3GameRuntimeChannel` - Browser side of the runtime control channel;
  `connect`, `disconnect`, `dispatch`, `getHistory`. It always installs
  `globalThis.__A3GAME_RUNTIME__`, which is how generated tests drive
  commands deterministically.
- `bootA3GameRuntime` - Boots host, assets, world, HUD, session, and
  runtime in the conventional order.

## Framework Boundaries

`A3GamePlayable` provides runtime contracts and engine scaffolding only.
It does not provide a concrete Character, Pawn, Controller, GameMode, HUD
content, weapon, vehicle, combat rule, scoring rule, or game-specific
input mapping.

Generated projects own concrete gameplay implementation. The Arena
Fighter, FPS, and Racing example packages are read-only references and
are not dependencies or success criteria.

## Web-Specific Obligations

These have no UE5 equivalent and are the most common failure modes in
generated three.js games:

1. **Dispose explicitly.** three.js never frees GPU memory. Every entity
   must dispose its geometries, materials, and textures; use
   `disposeObject3D(root)`.
2. **Never hard-code URLs.** Resolve every asset through
   `A3GameAssetLibrary` and every world through `A3GameSceneLoader`.
3. **Frame-rate independence.** Multiply by the tick delta. Never assume
   60Hz.
4. **Colour space.** Colour textures need `SRGBColorSpace`; data textures
   (normal, roughness, metalness, AO) must not.
5. **Lighting is required.** A world with no light and no environment map
   renders PBR materials black.
6. **Pointer lock needs a gesture.** `PointerLockControls.lock()` must be
   called from a user event, not at boot.
7. **One render loop.** Subscribe with `host.onTick`; never call
   `requestAnimationFrame` in gameplay code.
8. **Testability over screenshots.** Assert `getRuntimeSnapshot()`,
   `hud.getState()`, and rule state; drive input through
   `globalThis.__A3GAME_RUNTIME__`.
