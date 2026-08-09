# A3GamePlayable (three.js)

Runtime extension contracts for generated three.js gameplay packages.
This is the adapter-owned framework; it is the web counterpart of the
UE5 `A3GamePlayable` plugin.

Install it with the public adapter API, never by copying files:

```python
from engine_adapters.three_js import ThreeClient

three = ThreeClient(project_path="/path/to/project")
three.plugin.install_framework()
```

## Import surface

```js
import {
  A3GameRuntimeHost,
  A3GameEnvironmentPreset,
  A3GameAssetLibrary,
  A3GameSceneLoader,
  A3GameInputRouter,
  A3GameLookMode,
  A3GameAnimationDirector,
  A3GameCollisionProbe,
  A3GameHudLayer,
  A3GameMaterialPreset,
  A3GameRuntimeSubsystem,
  A3GameWorldSessionSubsystem,
  A3GameRuntimeEntityComponent,
  A3GameEntityFactory,
  A3GameControllableEntity,
  bootA3GameRuntime,
  createContactShadow,
  createFillLight,
  createMaterial,
  createRoundedBox,
  createSeededRandom,
  createSunLight,
  disposeObject3D,
  fitToHeight,
  groundObject,
  measureObject,
  prepareModel,
  resolveEntityId,
} from '@a3game/playable';
```

Deep imports into `src/` are not part of the contract. `three` is a peer
dependency supplied by the host project.

## Choosing a collision primitive

three.js ships no physics engine, so `A3GameCollisionProbe` supplies the
primitives every generated game needs. Picking the wrong one is the most
common gameplay bug:

| Question | Primitive |
| --- | --- |
| What is under me? | `sampleGround` |
| Can I move there? | `resolveMove` / `stepCharacter` |
| What did I shoot, instantly? | `hitscan` |
| What is **near** me? | `overlapSphere` |
| Where did my projectile go this frame? | `sweepSphere` |

`overlapSphere` treats a target with no geometry as a point at its world
position, so bare `Object3D` markers work as triggers. `sweepSphere`
tests the whole travelled segment, so a fast projectile cannot tunnel
through a thin wall.

## Cameras

`A3GameRuntimeHost` supports both projections. Pass
`cameraType: 'orthographic'` (with `frustumHeight`) for a side-scrolling
or isometric game, or switch at runtime with `useOrthographicCamera()` /
`usePerspectiveCamera()`. `setFrustumHeight()` rescales an orthographic
view cheaply enough to call every frame.

For a first-person game that derives `yaw`/`pitch` from the input frame,
use `requestPointerLock()` rather than `attachPointerLockControls()`:
`PointerLockControls` writes the camera itself, and two authors fighting
over one camera produces jitter.

## Looking good without art

three.js ships no models, so a generated game's appearance comes from
these calls rather than from finding an asset:

```js
host.setEnvironment({
  preset: 'sky',                // or 'room' for an interior
  sunPosition: sunDirection,
  toneMapping: 'ACESFilmicToneMapping',
  toneMappingExposure: 0.7,
});
host.add(createSunLight({ radius: 120 }), 'lights');   // fitted shadows
host.add(createFillLight(), 'lights');
const prop = createRoundedBox({ width: 2, depth: 4, preset: 'painted_metal' });
```

`setEnvironment({ preset })` generates image-based lighting on the GPU
from `RoomEnvironment` or the `Sky` shader — no `.hdr` file, no licence.
It matters more than any other single call: without an environment map a
PBR material has nothing to reflect and reads as flat plastic no matter
how it is lit.

`createSunLight` exists because the stock `DirectionalLight` shadow
camera is a 10-metre box at the origin, so a large map gets no shadow at
all; it also prefers `normalBias`, which scales with the geometry, over a
flat `bias` that is only correct at one distance.

`A3GameMaterialPreset` keeps materials physically honest: a surface is a
conductor or it is not, so dielectrics stay at `metalness: 0` and get
their shine from `clearcoat`.

## Imported models

`GLTFLoader` output is never scene-ready, so both loading helpers run
`prepareModel` for you:

```js
// Build-from-scratch content: use the model, or the primitive version.
const built = await assets.instantiateOrBuild('robot_expressive',
  () => buildPrimitiveBody(), { height: 1.8, ground: true });

// Existing content being upgraded.
const loaded = await assets.tryInstantiate('fox', { height: 0.85 });
if (loaded) entity.setVisual(loaded.object, loaded.animations);
```

Two problems have no glTF-level solution and are handled there:

- **scale** — every model arrives in the author's unit of choice, so
  normalise with `height` rather than a magic constant;
- **shadows** — glTF cannot express `castShadow`, so every mesh loads
  with it false.

Set `frustumCulled: false` on a skinned character, which is otherwise
culled on its bind-pose bounds and blinks out at the screen edge.

## Tick ordering

`A3GameRuntimeSubsystem.onWorldBeginPlay()` installs the tick that
delivers queued input to entities. Register `input.pipeToSession()` — and
any AI that enqueues frames — *before* it, or every input frame arrives
one frame late. `bootA3GameRuntime({ autoBeginPlay: false })` hands that
ordering to the game.

## Assets are optional

`A3GameAssetLibrary.load()` tolerates a missing manifest and records the
reason in `warnings`, because a procedurally built game imports nothing.
Check `assets.available` before reaching for an artifact, or pass
`requireManifest: true` when the game genuinely cannot run without
imported content.

## What the framework owns

| Layer | Responsibility |
| --- | --- |
| `data-types/` | Generic runtime data contract, identical wire format across Python and the browser |
| `interfaces/` | The three contracts generated gameplay implements |
| `components/` | Runtime identity and entity state attached to a `THREE.Object3D` |
| `subsystems/` | Session ownership, input arbitration, runtime coordination |
| `engine/` | Renderer, frame loop, asset manifest, world scene graph, input, animation, raycast probes, HUD, control channel |

## What the framework does not own

No Character, Pawn, Controller, GameMode, HUD content, weapon, vehicle,
combat rule, scoring rule, or game-specific input mapping. Generated
Gameplay Packages own all of that.

## Minimal generated gameplay

```js
import * as THREE from 'three';
import {
  A3GameControllableEntity,
  A3GameEntityFactory,
  A3GameRuntimeEntityComponent,
} from '@a3game/playable';

class MyPawn extends A3GameControllableEntity {
  constructor(object) {
    super();
    this.object = object;
    this.runtime = new A3GameRuntimeEntityComponent(object);
  }

  getRuntimeEntityId() {
    return this.runtime.entityId;
  }

  setRuntimeEntityId(entityId) {
    this.runtime.setRuntimeEntityId(entityId);
  }

  applyRuntimeInput(inputState) {
    // Concrete movement rules belong here, not in the framework.
    return this.runtime.applyRuntimeInput(inputState);
  }

  getRuntimeSnapshot() {
    return this.runtime.getRuntimeSnapshot();
  }
}

export class MyEntityFactory extends A3GameEntityFactory {
  async spawnRuntimeEntity(request, { host, assets }) {
    const { object } = await assets.instantiate(
      request.parameters.avatarArtifactId,
    );
    host.add(object, 'entities');
    return new MyPawn(object);
  }
}
```

## Resource discipline

three.js never frees GPU memory automatically. Every entity must release
its own geometry, materials, and textures; `disposeObject3D(root)` does
the traversal. Forgetting this is the most common failure in generated
web games.

A second, quieter trap: a raycast reads `matrixWorld`, and the renderer
only refreshes it at render time. An object that spawns or moves and is
probed in the same frame must call `object.updateMatrixWorld(true)`
first, or it is tested at the origin.
