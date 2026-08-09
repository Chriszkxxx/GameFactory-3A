# three.js Agent API Reference

Status: implemented `ThreeClient` API version `v1`.

Validated engine baseline: three.js r185 (`three@0.185.0`), Node 20,
Vite 6.

This file is a compact index of implemented public capabilities. It lists
public names and their functions only. Read the current source when exact
parameters or result payload fields are required.

## Toolchain

The three.js adapter has no engine installation. Its only external
requirement is a **Node 20+** toolchain on `PATH`, because the adapter
drives Vite, Vitest, and the package manager through its private Node
transport.

`scripts/three_js/setup_env.sh` provisions that toolchain as a conda
environment for machines with no system Node:

```bash
scripts/three_js/setup_env.sh                # create or verify
source <conda_root>/etc/profile.d/conda.sh
conda activate threejs
```

`scripts/three_js/README.md` documents the launchers and their environment
variables. Every launcher is a thin wrapper over the public
`ThreeClient`.

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

`scripts/three_js/import_asset` is a lifecycle wrapper around the same
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
  `remove`, `getRoot`, `usePerspectiveCamera`, `useOrthographicCamera`,
  `setFrustumHeight`, `attachOrbitControls`, `attachPointerLockControls`,
  `requestPointerLock`, `exitPointerLock`, `isPointerLocked`,
  `detachControls`, `setEnvironment`, `setFog`, `raycastFromPointer`,
  `raycast`, `captureFrame`, `getStats`, `dispose`.
- `disposeObject3D` - Recursively disposes geometries, materials, and
  textures.
- `A3GameAssetLibrary` - Loads the asset manifest and resolves artifacts;
  `load`, `has`, `findEntry`, `requireEntry`, `listByType`,
  `loadArtifact`, `instantiate`, `applyMaterialBinding`, `dispose`.
- `A3GameSceneLoader` - Builds a scene from a published world scene
  graph; `loadWorld`, `buildWorld`, `getEntityObject`,
  `resolveSpawnTransform`, plus `collisionTargets` and `spawnPoints`.
- `A3GameInputRouter` - Converts keyboard, pointer, and gamepad events
  into normalized input frames; `enable`, `disable`, `reset`, `onAction`,
  `isActionHeld`, `setLook`, `sample`, `pipeToSession`.
  `DEFAULT_KEY_BINDINGS` maps WASD/arrows, Shift, and Space.
- `A3GameLookMode` - Selects how mouse movement becomes look input:
  `POINTER_LOCK` (default, first person), `DRAG` (third person, cursor
  stays usable), `ALWAYS` (debug and headless tests).
- `A3GameAnimationDirector` - Wraps `AnimationMixer`; `addClip`,
  `addClips`, `listClipNames`, `mapState`, `mapStates`, `play`,
  `playOnce`, `stopAll`, `update`, `attachToHost`, `getState`,
  `dispose`.
- `A3GameCollisionProbe` - Raycast and volume primitives that stand in
  for the physics engine three.js does not ship; `setTargets`,
  `addTarget`, `removeTarget`, `sampleGround`, `resolveMove`,
  `stepCharacter`, `hitscan`, `overlapSphere`, `sweepSphere`.
- `resolveEntityId` - Walks up an `Object3D` hierarchy for the nearest
  runtime entity id, which is how every probe names what it found.
- `A3GameHudLayer` - DOM overlay HUD; `addText`, `addBar`, `addPanel`,
  `addBanner`, `addCrosshair`, `setValue`, `setValues`, `setVisible`,
  `remove`, `getState`, `dispose`. Widgets sharing an anchor stack in a
  column instead of overlapping. Every widget writes `data-a3game-*`
  attributes so end-to-end tests assert HUD state without screenshots.
- `A3GameRuntimeChannel` - Browser side of the runtime control channel;
  `connect`, `disconnect`, `dispatch`, `getHistory`. It always installs
  `globalThis.__A3GAME_RUNTIME__`, which is how generated tests drive
  commands deterministically.
- `bootA3GameRuntime` - Boots host, assets, world, HUD, session, and
  runtime in the conventional order.

### Choosing a Collision Primitive

Picking the wrong one is the most common gameplay bug in a generated
three.js game.

| Question | Primitive |
|---|---|
| What is under me? | `sampleGround` |
| Can I move there? | `resolveMove` / `stepCharacter` |
| What did I shoot, instantly? | `hitscan` |
| What is **near** me? (pickups, melee arcs, chests, checkpoints, triggers) | `overlapSphere` |
| Where did my projectile go this frame? | `sweepSphere` |

`overlapSphere` treats a target with no geometry as a point at its world
position, so bare `Object3D` markers work as triggers. `sweepSphere`
tests the whole travelled segment, which is what stops a fast projectile
tunnelling through a thin wall.

### Boot Options

`bootA3GameRuntime` accepts `container`, `hudContainer`, `manifestUrl`,
`worldUrl`, `worldId`, `hostOptions`, `entityFactory`, and:

- `requireManifest` - fail instead of warning when no asset manifest
  exists. Default `false`;
- `createHud` - suppress the built-in HUD layer. Default: create one when
  `hudContainer` is given;
- `autoBeginPlay` / `autoStart` - hand tick ordering and loop start to
  the game. Both default `true`.

It returns `{ host, assets, sceneLoader, hud, session, runtime, world }`.
Reuse `context.hud`; constructing a second `A3GameHudLayer` on the same
container stacks two overlay roots and makes `getState()` ambiguous.

### Building Without Imported Assets

A mechanic or prototype task often has no `.glb` to import. That is a
supported configuration:

- pass `requireManifest: false`, and check `assets.available` before
  reaching for an artifact;
- build content from three.js primitives (`BoxGeometry`,
  `CapsuleGeometry`, `CylinderGeometry`, `ConeGeometry`, extruded
  ribbons, displaced `PlaneGeometry`);
- draw textures into a `<canvas>` and wrap them in `CanvasTexture` rather
  than hard-coding an image URL — but keep that inside the build
  function, so headless tests can import the module;
- generate scenery from a **seeded** pseudo-random sequence, never
  `Math.random`, so the world is identical on every reload and in tests;
- still declare lights. A world with no light renders every PBR material
  black regardless of how the geometry was made.

A procedurally built game also skips `A3GameSceneLoader`: it owns its own
`buildX(host)` function and returns its own collision-target list.

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
   60Hz. For smoothing and decay use `Math.exp(-k * delta)` rather than a
   per-frame constant such as `value *= 0.9`.
4. **Colour space.** Colour textures need `SRGBColorSpace`; data textures
   (normal, roughness, metalness, AO) must not.
5. **Lighting is required.** A world with no light and no environment map
   renders PBR materials black.
6. **Pointer lock needs a gesture.** Call `host.requestPointerLock()`
   from a click or key handler, never at boot.
7. **One camera author.** `PointerLockControls` writes the camera every
   pointer event. A game that derives `yaw`/`pitch` from the input frame
   must use `requestPointerLock()` instead of
   `attachPointerLockControls()`, or the two fight each frame and the view
   jitters.
8. **One render loop.** Subscribe with `host.onTick`; never call
   `requestAnimationFrame` in gameplay code.
9. **Update the world matrix before probing.** A raycast reads
   `matrixWorld`, and the renderer only refreshes it at render time. An
   object that spawns or moves and is probed in the same frame must call
   `object.updateMatrixWorld(true)` first, otherwise it is tested at the
   origin. `overlapSphere` and `sweepSphere` handle their targets, but a
   moving entity must maintain its own.
10. **Tick order decides input latency.** The runtime subsystem's tick
    consumes queued input. Register `input.pipeToSession()` and any AI
    that enqueues frames *before* `runtime.onWorldBeginPlay()`; boot with
    `autoBeginPlay: false` when the game needs that control. Otherwise
    every input frame arrives one frame late.
11. **Speed caps are not forces.** Terminal speed comes from the
    force/drag balance, so a power-up that only raises a `maxSpeed` clamp
    does nothing. Change the acceleration too.
12. **Testability over screenshots.** Assert `getRuntimeSnapshot()`,
    `hud.getState()`, and rule state; drive input through
    `globalThis.__A3GAME_RUNTIME__`.

## Generated Test Pattern

Generated tests run under `vitest` in the `node` environment: no GPU, no
canvas, no screenshots. The reliable shape is:

1. build the entity directly against a small **host double** that
   implements only `add`, `getRoot`, `onTick`, and `camera`;
2. build an `A3GameCollisionProbe` over plain geometry, and call
   `updateMatrixWorld(true)` on it;
3. drive the entity with `createRuntimeInputState({ ..., sequence })` —
   the sequence must increase, or the frame is dropped as out of order;
4. step with an explicit delta;
5. assert the observable snapshot and rule state, and assert that state
   survives `JSON.stringify`.

Make test geometry generously larger than the distance the entity can
travel during the test. A car that drives off the edge of its test plane
silently becomes "airborne", and every surface assertion then reports the
wrong answer.

## Generated Output Layout

A generated playable game is a self-contained Vite project written to the
task output directory resolved by `pipeline/common/paths.py`:

```text
test_data/outputs/<game_id>/<run_id>/mechanic/<task_id>/
├── package.json          three + vite + vitest, `packages/*` workspace
├── vite.config.jsaliases @a3game/playable and the game package
├── index.html            #a3game-viewport, #a3game-hud, boot overlay
├── src/main.js           imports the Gameplay Package, nothing else
├── launch.sh             dev | build | preview | test
├── public/assets/        manifest.json (empty when nothing is imported)
└── packages/
    ├── a3game-playable/  installed by three.plugin.install_framework
    └── <game-name>/      the generated Gameplay Package + tests
```

Create the project with `three.project.create` (or
`scripts/three_js/create_project.sh`) and let
`three.plugin.install_framework` place the framework. Never copy the
framework by hand, and never build these paths by string concatenation.

## Serving a Game for Review

The dev server binds `127.0.0.1`, which is invisible from any other
machine — the usual reason a reviewer "cannot open the game". Generated
projects therefore read two environment variables:

- `A3GAME_DEV_HOST` — set to `0.0.0.0` to accept outside connections;
- `A3GAME_DEV_PORT` — override the per-game port.

`vite.config.js` also sets `allowedHosts: true`, because Vite 6 rejects a
request whose `Host` header it does not recognise, which is exactly what
an SSH forward or tunnel produces. Through the adapter the same switch is
`ThreeClient(host="0.0.0.0")`, or `run.sh --dev-host 0.0.0.0`.

Nothing about this needs a GPU or a display on the server: WebGL runs in
the reviewer's browser, and the server only serves modules. That is why
headless verification here is `vitest` plus `vite build`, never a
screenshot.
