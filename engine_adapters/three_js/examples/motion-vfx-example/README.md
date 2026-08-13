# Motion And Effects Reference

Two capabilities that a generated three.js game needs and that three.js
itself does not provide: **motion on an imported character**, and
**particle effects**. This package is the read-only reference for both.
Nothing here is installed automatically, and a generated game must adapt
the patterns inside its own Gameplay Package.

| File | Read it for |
| --- | --- |
| `src/motion.js` | Getting a generated character to move at all, and refusing one that cannot |
| `src/effects.js` | Batched particles, tracer beams, projectile trails, intensity-driven streams |

## Why this exists

Both halves replace a mistake that is easy to make and hard to see.

**Motion.** `assets.tryInstantiate` is correct for a *downloaded*
character and silently wrong for a *generated* one. Image-to-3D produces
one fused body, so the manifest entry reports `animations: []` and
`skinned: false`. A game that swaps its procedural body for such a model
gets a good-looking character that never moves — worse than the capsule it
replaced, because the primitive limbs that *were* being posed went away
with the swap.

**Effects.** One `Sprite` per spark is one draw call per spark, plus a
second animation loop and nothing disposed, so a firefight degrades the
frame rate in proportion to how well the fight is going.

## Importing motion through the adapter

Motion is staged like any other asset, from a repository task identity —
never from a filesystem path:

```python
from engine_adapters.three_js import ThreeClient

three = ThreeClient(project_path="/path/to/project")

# A clip produced by pipeline/assets_gen/gen_motion.
three.assets.import_motion(
    {"game_id": "game_fps_pistol_arena", "run_id": "default",
     "task_kind": "assets", "task_id": "trooper_walk"},
    options={"asset_id": "trooper_walk"},
)

# Or through the Animation namespace, against a target skeleton, which also
# reports whether the clip can drive that avatar without retargeting:
three.animation.import_motion(task_identity, options={"asset_id": "trooper_walk"})
three.animation.resolve_skeleton("arena_trooper")
three.animation.validate_compatibility("arena_trooper", "trooper_walk")
```

Staged motion lands in `public/assets/imported/motions/` and appears in
the manifest as `type: "motion"`. `A3GameMotionLibrary` is what finds it
at runtime — a motion file carries clips and usually a skeleton but no
renderable body, so it is not something `instantiate()` can return.

The full generation chain is documented in
`agent_skills/asset_qa/motion_gen_skills.md`: rig with Puppeteer, generate
with MoMask or fetch a licensed clip, retarget with the Blender
`world_delta` step, then verify with `inspect_fbx` and refuse anything
whose `pose_animated` is false. Convert the retargeted FBX to glTF before
staging it: `fbx` loads in the browser but validates with a warning, and
`glb` is the runtime format.

## Importing effect content through the adapter

An effect authored elsewhere — a texture atlas, a flipbook, a JSON effect
description — is staged with `import_effect`:

```python
three.assets.import_effect(
    {"game_id": "game_archer_explorer", "run_id": "default",
     "task_kind": "assets", "task_id": "spark_atlas"},
    options={"asset_id": "spark_atlas"},
)
```

It lands in `public/assets/imported/effects/`. Pass the loaded texture to a
particle system as `map`, with `flipbook` rows and columns if it is an
atlas.

Most effects need no import at all, and that is the intended path: the
shape mask is computed in the fragment shader, so a spark, a muzzle flash,
and a smoke puff cost no download and carry no licence. Import only when a
specific authored look is required.

## Runtime API

Everything below comes from `@a3game/playable`:

```js
import {
  createAnimatedActor,      // the whole motion chain in one call
  A3GameMotionLibrary,      // staged `type: 'motion'` artifacts
  autoRigHumanoid,          // fit a skeleton to a static humanoid mesh
  createHumanoidClipSet,    // authored walk/run/punch/kick/aim/shoot/…
  retargetClipToSkeleton,   // rename tracks onto another skeleton
  measureHumanoid,          // is this mesh a standing figure at all?
  createVfxDirector,        // batched owner of every effect
  A3GameVfxPreset,          // tuned effect definitions
  A3GameParticleSystem,     // one pooled effect, one draw call
  A3GameBeamEffect,         // pooled tracer lines
  A3GameTrailRibbon,        // continuous streak behind a projectile
} from '@a3game/playable';
```

### The motion decision, in one call

```js
const actor = await createAnimatedActor(assets, 'arena_trooper', {
  height: 1.8,
  ground: true,                       // place by the feet, not the origin
  states: ['idle', 'walk', 'run', 'aim', 'shoot', 'hit', 'death'],
  defaultState: 'idle',
});

if (!actor || actor.motionSource === 'none') {
  // Keep the procedural body. It moves, and this one does not.
} else {
  entity.setVisual(actor.object, actor.animations, {
    animator: actor.animator,
    motionSource: actor.motionSource,
  });
}
```

`motionSource` is one of `clips`, `imported_motion`, `auto_rig`, or
`none`, and every branch above is load-bearing. `none` is returned for a
mesh whose proportions are not a standing figure — the characteristic
output of a reconstruction that invented a ground plane — and honouring it
is the difference between a game that looks generated and one that stands
still forever.

### Naming clips as a list, not a name

```js
animator.mapStateChains({
  idle: ['idle', 'Idle', 'Standing'],
  attack: ['aim', 'ThumbsUp', 'Idle'],
});
```

The authored set calls the shooting stance `aim`; the CC0
`robot_expressive` avatar has fourteen clips and none of them is called
that. A single name means one of the two sources plays nothing.

### Effects

```js
const vfx = createVfxDirector({ host, presets: { … } });   // attached to the tick

vfx.play('bullet_impact', { position: hit.point, direction: hit.normal });
vfx.fireBeam('player_tracer', muzzleWorldPosition, hit.point);
const handle = vfx.follow('tyre_smoke', rearAxleMarker, { rate: 90 });
```

Three placement rules decide whether an effect reads at all:

1. **A burst points along the surface normal**, not along the shot.
   Sparks that continue into the wall cannot be seen, which is why
   `A3GameCollisionProbe.hitscan` returns a world-space `normal`.
2. **A tracer starts at the muzzle**, not at the camera. A line drawn from
   the eye is inside the near plane and invisible.
3. **A trail is not parented to what it follows.** A parented trail is
   dragged along by the object, so the streak never forms behind it —
   `follow()` moves the *emitter* and leaves the particles in world space.

## Boundaries

The framework is adapter-owned: a generated game may not modify it, may
not deep-import `@a3game/playable/src/...`, and may not depend on this
example package. Effects are decoration and must never be load-bearing —
`play()` on an unregistered name returns `0` rather than throwing, so a
missing effect can never be the reason a hit stops registering.
