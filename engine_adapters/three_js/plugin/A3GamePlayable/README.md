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
  A3GameAssetLibrary,
  A3GameSceneLoader,
  A3GameInputRouter,
  A3GameAnimationDirector,
  A3GameCollisionProbe,
  A3GameHudLayer,
  A3GameRuntimeSubsystem,
  A3GameWorldSessionSubsystem,
  A3GameRuntimeEntityComponent,
  A3GameEntityFactory,
  A3GameControllableEntity,
} from '@a3game/playable';
```

Deep imports into `src/` are not part of the contract. `three` is a peer
dependency supplied by the host project.

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
