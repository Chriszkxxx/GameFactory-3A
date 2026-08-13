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

`three.preview.*` is not execution and the Agent may call it freely: it
renders an artifact on the CPU to inform a decision, produces no
benchmark claim, and writes nothing a player downloads.

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
- `three.assets.set_orientation` - Records which way a staged model faces
  and how big it is meant to be.
- `three.assets.get_orientation` - Reads back one artifact's recorded
  orientation.
- `three.assets.analyze_orientation` - Reports what geometry alone says
  about a model's facing, for a staged artifact or an unstaged task
  identity.

Public asset methods consume repository task identities. They do not
accept arbitrary generated-output filesystem paths.

### Asset Orientation

glTF fixes the up axis (+Y) and the unit (metre) and says nothing binding
about **facing**. A model authored facing +Z and the same model facing -Z
have identical bounding boxes, node trees and animation clips, so no
amount of loading can tell them apart. The runtime convention is:

```text
local forward = -Z·   local up = +Y
```

That is what a yaw of zero means to generated gameplay, which derives
facing with `Math.atan2(-x, -z)`. A model that disagrees is not broken —
it is unlabelled, and the label is carried in the artifact record:

```python
three.assets.import_prop(source, options={
    "asset_id": "chest", "forward_axis": "+z",
    "scale_hint_metres": 0.8, "verified_by": "agent_vision",
})
# or afterwards, without re-staging the file:
three.assets.set_orientation("chest", forward_axis="+z",
                             scale_hint_metres=0.8,
                             verified_by="agent_vision")
```

`forward_axis` names the axis the model faces *as authored*; the adapter
derives the yaw, so no caller computes an angle. `+z → 180°`,
`-z → 0°`, `+x → 90°`, `-x → 270°`. Also available:
`yaw_offset_degrees` for a model facing no cardinal axis,
`pitch_offset_degrees` for content authored Z-up, `scale_hint_metres`,
`pivot`, `verified_by` (`unverified`/`heuristic`/`declared`/
`agent_vision`/`human`) and `notes`.

Importing a directional asset without a `forward_axis` succeeds and
returns a warning: the runtime then places the model exactly as authored,
which is a coin flip. Determining the axis requires looking at the model —
see **Preview** below and
`agent_skills/asset_qa/imported_asset_orientation.md`.

All three models in the curated CC0 pack face **+Z**, so every one of
them needs a 180° correction.

## Preview

- `three.preview.render_artifact` - Renders a staged artifact from named
  axes and writes labelled PNGs plus one contact sheet.
- `three.preview.render_source` - Renders a repository task artifact
  before it is imported.
- `three.preview.orientation_report` - Renders the review sheet and
  returns it with the geometric evidence and the exact call that records
  a decision.
- `three.preview.list_views` - Reports the view sets and what each
  rendered axis means.

The renderer is pure `numpy` and `Pillow`: no GPU, no display, no
browser, no Node process, and about two seconds per asset. Views are
**orthographic** and named after the axis the camera sits on — a view
labelled `+z` shows the model's +Z side — because naming a view "front"
would presuppose the answer being sought. Each image carries its axis and
its screen-right axis burnt into the frame, since a filename is invisible
to a reader handed only pixels.

Renders land under the project's `.a3game/previews/`, never in `public/`:
they are review evidence, not shipped content.

Geometry is decoded in the **bind pose**, with a skinned mesh's node
transform ignored as the specification requires, so the review measures
the model rather than a frame of its walk cycle. Draco- and
meshopt-compressed artifacts cannot be decoded without a GPU decoder and
report that instead of drawing nonsense.

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
      "bounds": { "min": [], "max": [], "size": [], "center": [] },
      "orientation": {
        "forward_axis": "+z", "up_axis": "+y",
        "yaw_offset_degrees": 0, "runtime_forward_axis": "-z",
        "runtime_yaw_degrees": 180, "scale_hint_metres": 1.8,
        "verified_by": "agent_vision", "needs_vision_check": false
      }
    }
  }
}
```

`orientation` is what `A3GameAssetLibrary` applies at instantiation. An
absent or empty block means nobody recorded a facing, and the runtime
then leaves the model exactly as authored — so annotating an asset can
never make an already-correct game worse.

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
- `A3GameEnvironmentPreset` - Procedural image-based lighting selected by
  `setEnvironment({ preset })`: `ROOM` (interiors), `SKY` (a physical sky
  that also becomes the backdrop), `NONE`. Generated on the GPU at boot,
  so no `.hdr` is downloaded and no licence applies.
- `disposeObject3D` - Recursively disposes geometries, materials, and
  textures.
- **Visual kit** - the look-and-feel building blocks, all game-neutral:
  `createMaterial` with `A3GameMaterialPreset` (metal, painted_metal,
  gunmetal, plastic, rubber, cloth, leather, wood, stone, concrete,
  tarmac, grass, sand, glass, emissive), `createRoundedBox`,
  `createSunLight` (shadow camera fitted to a radius), `createFillLight`,
  `createContactShadow`, `createRadialGradientTexture`,
  `createSeededRandom`, `createInstancedFromModel` (one draw call for many
  copies of one generated body), plus the imported-model utilities
  `prepareModel`,
  `orientModel`, `forwardAxisYaw`, `A3GameForwardAxis`,
  `A3GAME_RUNTIME_FORWARD_AXIS`, `fitToHeight`, `groundObject`, and
  `measureObject`.
- `A3GameAssetLibrary` - Loads the asset manifest and resolves artifacts;
  `load`, `has`, `findEntry`, `requireEntry`, `listByType`,
  `loadArtifact`, `instantiate`, `tryInstantiate`, `instantiateOrBuild`,
  `applyMaterialBinding`, `dispose`.
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

### Making a Generated Game Look Good

three.js ships **no 3D models** in its npm package — only loaders and
procedural helpers. So a generated game's appearance is decided by the
framework calls below, not by finding a model to load. In rough order of
visible effect per line of code:

1. **An environment map.** `host.setEnvironment({ preset: 'room' })` for
   an interior, `{ preset: 'sky' }` for outdoors. Both are generated on
   the GPU at boot — no `.hdr` download, no licence. Without one, every
   PBR material has nothing to reflect and reads as flat plastic however
   many lights are added. This is the single largest factor.
2. **Filmic tone mapping.** `toneMapping: 'ACESFilmicToneMapping'` with
   an exposure near 0.7 outdoors. The default clips highlights to white.
3. **A fitted shadow camera.** `createSunLight({ radius })`. The stock
   `DirectionalLight` shadow camera is a 10-metre box at the origin, so a
   200-metre track gets no shadow at all.
4. **Bevelled edges.** `createRoundedBox()` instead of `BoxGeometry`. A
   mathematically sharp edge cannot catch a highlight; nothing
   manufactured has one.
5. **Honest materials.** `createMaterial('painted_metal')` and friends.
   `metalness: 0.5` describes no real substance — a surface is a
   conductor or it is not. Car paint is a dielectric with a clearcoat.
6. **Contact shadows.** `createContactShadow()` grounds an object for one
   draw call, and works with shadow maps switched off.

Only then does imported art help, and it only helps if it is
*game-ready*. Two things decide that, and both are recorded per artifact
rather than guessed at runtime: it has to be the right size, and it has
to face the right way. A generated mesh at the wrong scale reads as a
toy; one facing the wrong way makes the character strafe for its entire
walk cycle. Neither is a rendering problem, and no lighting change hides
either.

### Sourcing Imported Models

three.js ships no models, so there are exactly two ways to get one, and
they are not interchangeable.

**Generate it** — `Gen3DObjectOperator.run_art_plan`, driving TRELLIS.2
through `models/gen_3d_object/trellis_2_model.py`. This is the default for
a game's own content, because it produces the props the design asked for
rather than the three that happen to be free:

```python
from models.gen_3d_object.trellis_2_model import Trellis2Model
from operators.gen_3d_object.operator import Gen3DObjectOperator

op = Gen3DObjectOperator(model=Trellis2Model(model_path="…/TRELLIS.2-4B"))
op.run_art_plan("game_archer_explorer", image_model=qwen_edit)
```

Each entry of the art plan
(`operators/gen_3d_object/funcs/art_plan.py`) names a subject, an asset
type, **a height in metres**, and a **role**. The operator generates a
concept image, reconstructs it, strips the floor the reconstruction
invents, writes an ordinary `3d_object` task output, imports it, and
renders the review sheet.

Its budgets differ from the model wrapper's showcase defaults, and the
role is what picks them — because what costs a frame is how *often* a
thing is drawn, not what it is:

| Role | Triangles | Texture |
|---|---|---|
| `avatar` | 40 000 | 2048 |
| `weapon` / `prop` / `landmark` | 20 000 | 1024 |
| `scenery` (repeated dozens of times) | 8 000 | 1024 |
| *model wrapper default* | *1 000 000* | *4096* |

A million-triangle chair spends a frame budget where nobody looks, and a
4K atlas is 16 MB of download per prop. Get this right **before**
generating: a textured mesh cannot be decimated afterwards without
throwing its UVs away, because TRELLIS.2 bakes the texture after it
decimates.

`forward_axis` is recorded as `+z` with `verified_by="heuristic"`, so
`needs_vision_check` stays true until an agent looks. A guess labelled as
verified is worse than no record, because it stops anyone checking.

Expect a **floor** in the raw output. Image-to-3D crops its input to the
subject's silhouette, so a standing figure touches the frame edge and the
model infers a ground plane — a fifth of the triangle budget, and a 2.4 m
grey pancake once scaled to a character. `funcs/mesh_cleanup.py` removes
it as part of every run and reports what it took; it refuses when the
diagnosis would cost more than 40% of the mesh, on the grounds that the
object is then genuinely a flat thing.

Prompts must describe **one object, facing the camera, on a plain
background, uncropped, evenly lit**. That is not taste. Single-image
reconstruction turns the photographed side into a fixed axis of the
output, bakes cast shadows into the albedo permanently, invents whatever
the image did not show, and simply ends the mesh where a crop ended the
subject.

Generation is the wrong tool for anything that must **articulate**: the
output is one fused body, so a car's wheels cannot spin and a chest's lid
cannot open. Generate the shell, keep moving parts as primitives driven
by gameplay, and swap only the visual.

**Download it** — `operators/gen_3d_object/funcs/asset_pack.py`, a
curated, licence-checked pack of three CC0 models:

```python
from operators.gen_3d_object.funcs import fetch_asset_pack
fetch_asset_pack(games=["game_archer_explorer"])
```

Two upstream sources have terms clear enough to use: the
`mrdoob/three.js` example models, and `KhronosGroup/glTF-Sample-Assets`.
Judge a candidate on three things before staging it:

| Check | Why it decides the answer |
|---|---|
| Licence | CC0 and CC-BY are usable, with attribution recorded. CC-BY-**NC**, SCEA, and CryEngine terms are not. Mixamo-derived characters carry terms that do not travel with the file. |
| File size | A 17 MB prop with a 4K texture set that occupies fifty pixels is all download and no gain. A good character is a few hundred KB. |
| Node hierarchy | A model fused into **one mesh** cannot be animated by gameplay. A "car" whose wheels are part of the body can never steer or spin them, and looks worse than a bevelled primitive that can. |

Verified examples: `RobotExpressive.glb` (CC0, 456 KB, 14 clips, faces
+Z, 1.8 m subject) is an excellent character; `ToyCar.glb` (CC0, 5.4 MB)
is a beautiful *prop* and a useless vehicle, because it is a single mesh.

Both paths end the same way: an asset task output, a public
`ThreeClient.assets` import carrying `forward_axis` and
`scale_hint_metres`, and a review sheet. Neither copies a file into
`public/` itself.

### Loading Imported Models

Two calls cover every case, and both leave the game playable with an
empty manifest:

```js
// Content whose visual is built from scratch.
const { object, animations, source } = await assets.instantiateOrBuild(
  'robot_expressive',
  () => buildPrimitiveBody(),      // used when nothing is staged
  { height: 1.8, ground: true, envMapIntensity: 1 },
);

// Content that already exists and is being upgraded.
const loaded = await assets.tryInstantiate('fox', { height: 0.85 });
if (loaded) entity.setVisual(loaded.object, loaded.animations);
```

Both run `prepareModel`, which handles the three things every imported
model needs and no glTF can express:

- **Facing.** The manifest's `orientation.forward_axis` is applied by
  rotating the model inside a wrapper `Group`, and that wrapper is what is
  returned. The split matters: gameplay code and world specs both assign
  `rotation.y` on the object they are handed, so putting the correction on
  the same node would undo it on the first frame. Pass
  `{ forwardAxis: '+x' }` to override the manifest, or `{ orient: false }`
  to opt out.
- **Scale.** Every model arrives in whatever unit its author chose. Of
  three CC0 models staged for these games, one is 4.5 units tall, one is
  79, and one is 0.07. Pass `height`, or let the recorded
  `scale_hint_metres` supply it — never a magic constant.
- **Shadows.** glTF has no notion of casting shadows, so `GLTFLoader`
  leaves `castShadow` false on every mesh. A model that lights correctly
  but floats shadowless above the floor is the most common "why does my
  imported asset look wrong" symptom.

`A3GameSceneLoader` goes through the same path, so a published World gets
the orientation correction too.

Also set `frustumCulled: false` on a skinned character: it is culled on
its bind-pose bounds and otherwise blinks out at the screen edge.

Separate the gameplay transform from the drawn body — `entity.object`
carries position, facing, and the hit volume; `entity.visual` is a child
that `setVisual` can replace. Swapping a model then disturbs no physics,
and the procedural body remains the fallback that headless tests use.

Name **a list** of candidates, not one asset, wherever a game reaches for
art: `assets.has(['explorer_ranger', 'robot_expressive'])` prefers the
model generated for this game, accepts the CC0 stand-in, and falls through
to the procedural body. Which of the three happens is not a decision that
belongs in gameplay code, and a list keeps it out.

### Dressing A Scene With Generated Art

Swapping a *character* is one model. Dressing a *scene* is seventy-four
trees, and there the naive approach — one instantiated model per
placement — is what makes a generated game unplayable rather than
merely plain: seventy-four draw calls and seventy-four copies of the
geometry.

`createInstancedFromModel(model, count)` turns one prepared, non-skinned
model into an `InstancedMesh`, so a whole wood costs one draw call and one
copy of the geometry, with the per-copy transforms on the GPU. It returns
`null` for skinned or multi-part models rather than silently flattening
them, so a caller can fall back to what it was already drawing.

Two rules make this safe to retrofit into a finished game:

1. **Keep the primitive as the collision volume.** Clear its `visible`
   flag and leave it in the collision list. `Raycaster` does not test
   visibility and `Mesh.raycast` only requires a material, so an invisible
   box still stops an arrow — more cheaply than a 20 000-triangle prop
   would, and more fairly: cover that looks solid on screen *is* solid in
   the simulation.
2. **Never add a collider that was not there before.** Pure decoration —
   roadside palms, backdrop street furniture — must stay out of the
   collision list, or an art pass silently retunes the gameplay.

The four generated games each keep this in one function
(`dressScenery`, `dressArena`, `dressStage`, `dressTrack`) called straight
after the world is built, and each returns a count per kind so a test can
assert what happened.

### Building Without Imported Assets

A mechanic or prototype task often has no `.glb` to import. That is a
supported configuration:

- pass `requireManifest: false`, and check `assets.available` before
  reaching for an artifact;
- build content from three.js primitives (`createRoundedBox`,
  `CapsuleGeometry`, `CylinderGeometry`, `ConeGeometry`, extruded
  ribbons, displaced `PlaneGeometry`);
- draw textures into a `<canvas>` and wrap them in `CanvasTexture` rather
  than hard-coding an image URL — but keep that inside the build
  function, so headless tests can import the module;
- generate scenery from a **seeded** pseudo-random sequence
  (`createSeededRandom`), never `Math.random`, so the world is identical
  on every reload and in tests;
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
   renders PBR materials black. A world with lights but no environment map
   renders them flat: `setEnvironment({ preset })` is what supplies
   reflections.
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
12. **An imported model is never scene-ready.** glTF carries no scale
    convention, no shadow flags, and no facing convention, so a raw
    `instantiate()` yields a skyscraper or a speck, casting no shadow,
    pointing in an arbitrary direction. Go through
    `tryInstantiate`/`instantiateOrBuild` with a `height`, and record the
    facing axis with `three.assets.set_orientation` — never with a
    `rotation.y += Math.PI` inside an entity, which is invisible to every
    other consumer of that asset and is erased the moment the entity
    assigns its own facing.
13. **Testability over screenshots.** Assert `getRuntimeSnapshot()`,
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

The framework ships one test of its own,
`packages/a3game-playable/tests/orientation.spec.js`, installed by
`three.plugin.install_framework`. It appears in every generated project's
report and asserts the orientation contract — including that a game
assigning `visual.rotation.y` cannot undo a recorded facing correction.
Generated tests do not need to duplicate it; they must not break it.

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
