---
name: create-vfx-effects
description: Create and control reusable game VFX in Unreal Engine 5 or Unity, including smoke, fire, explosions, dust, stylized ink/frost/cyber effects, and action-attached effects. Use for environmental or combat VFX, Niagara, Unity ParticleSystem, VFX lifecycle, animation/socket binding, or engine code that must reuse an existing effect template.
---

# Create VFX Effects

Start from a reviewed Niagara System, particle prefab, or VFX Graph asset. The
adapters provide a common spawn and cleanup interface; Unity's procedural effects
are fallbacks for projects without a suitable asset.

## Select The Engine

- For UE5, read `engine_adapters/ue5/vfx/vfx_functions.py` and call its Python API
  inside Unreal Editor.
- For Unity, read
  `engine_adapters/unity3d/vfx/Runtime/A3Game_VFX.cs`. Copy it under the
  target project's `Assets/` directory before referencing the class.
- Keep engine-specific code out of host Python and model/operator modules.

For Mechanic tasks, `UEClient` remains the only host-side Unreal API. Use the VFX
modules as references for generated engine code or in an editor-side review step;
do not import them from the host Agent or bypass `UEClient` transport boundaries.

## Reuse Templates First

1. Search the project for an effect with the right silhouette and timing. In Unity,
   check `Assets/` and `%APPDATA%/Unity/Asset Store-5.x/`.
2. Tune exposed parameters, transforms, material instances, or colors on an
   instance. Leave the source template unchanged.
3. Pass a project-specific asset path or prefab when the documented default is not
   installed.
4. Fall back to Unity's procedural named functions only when no reviewed asset is
   available.

Do not substitute a glowing sphere or untextured white particles for smoke or fire.

## UE5 Functions

- Call `spawn_smoke`, `spawn_fire`, `spawn_explosion`, or `spawn_dust` for named
  effects.
- Call `spawn_niagara(system_path, ...)` for a project-specific template.
- Call `spawn_effect(kind, ...)` when the category is selected dynamically.
- Call `stop_effect(actor, destroy=True)` to clean up a looping effect.
- For ink, frost, or cyber, call `spawn_styled_effect`.
- For action-attached effects, build a WorldFlexVFXBinder request with
  `build_punch_fire_binding`; run detection with `Apply=false` before changing an
  animation asset.
- Treat locations as centimeters and rotations as `(pitch, yaw, roll)` degrees.

Natural-effect defaults:

| Kind | Default Niagara System |
|---|---|
| smoke | `/Game/NiagaraExamples/FX_Smoke/NS_Smoke_Plume` |
| fire | `/Game/NiagaraExamples/FX_Misc/NS_Fire` |
| explosion | `/Game/NiagaraExamples/FX_Explosions/NS_Explosion_Small` |
| dust | `/Game/NiagaraExamples/FX_Explosions/NS_Dirt_Explosion_Small` |

Stylized defaults and layer contracts:

| Style | Niagara System | Required layers | Material and palette |
|---|---|---|---|
| ink | `/Game/VFXGenEngine/SwapFX/NS_sp_ink` | quantized body, flow-distorted wash, droplets | 4-step values; slow two-phase flow; near-black and paper-lit gray |
| frost | `/Game/VFXGenEngine/SwapFX/NS_sp_ice` | cold core, crystal shards, camera glints | world-space noise glints; low distortion; cyan-white and deep blue |
| cyber | `/Game/VFXGenEngine/SwapFX/NS_sp_cyber` | energy body, pulse, data streaks | 4-step moving values; fast pulse/glitch; cyan and magenta |

These systems replace the stock `NS_Fire` renderer material with style-specific
material instances and post processing. A stock system plus parameter writes is
not equivalent because unsupported Niagara parameters are silent no-ops.

`build_punch_fire_binding` detects a high-speed hand interval and attaches a timed
Niagara notify state to `RightHand`. Run with `Apply=false`, inspect the event time,
duration, and scale, then apply to a copy or an approved animation asset.

Pass `system_path="/Game/..."` when a project installs an asset elsewhere. Missing
assets raise `VFXAssetNotFound`.

```python
from engine_adapters.ue5.vfx import spawn_fire, stop_effect

fire = spawn_fire(
    (120.0, -40.0, 0.0),
    scale=0.8,
    color=(1.0, 0.35, 0.05, 1.0),
)
stop_effect(fire, destroy=True)
```

Only set parameters exposed by the selected Niagara System. Unreal accepts writes
to unused parameters, so preview one instance before applying a batch change.

## Unity Functions

- Call `SpawnPrefab` for an existing particle prefab or compiled VFX Graph prefab.
- Call `SpawnSmoke`, `SpawnFire`, `SpawnExplosion`, or `SpawnDust` for the
  no-asset ParticleSystem fallback.
- For a smoke flipbook, set `SmokeOptions.particleMaterial` and
  `textureSheetTiles`. Use `forceAlphaBlend` only to correct a converted URP
  material; leave the package material unchanged.
- Call `Stop(root, immediate)` for looping smoke or fire.
- `SpawnInkSmoke`, `SpawnFrostFire`, and `SpawnCyberFire` are experimental
  fallbacks; the reviewed stylized baselines are the UE systems above.
- Treat positions and sizes as meters.
- Require the built-in `com.unity.modules.particlesystem` module. Add it to
  `Packages/manifest.json` when a stripped-down project has disabled it.

```csharp
using A3Game.EngineAdapters;

GameObject fire = firePrefab != null
    ? A3GameVFX.SpawnPrefab(
        firePrefab, transform.position, transform.rotation, Vector3.one, transform)
    : A3GameVFX.SpawnFire(transform.position, new FireOptions {
        loop = true,
        intensity = 1.2f
    }, transform);

A3GameVFX.Stop(fire);
```

## Validate The Result

- Preview at least one second with world ticking.
- Verify the effect reads as the requested category at gameplay camera distance.
- Verify looped effects stop and one-shot effects clean themselves up.
- Verify transparent smoke uses alpha blending and flame cores use additive or
  emissive rendering as appropriate.
- Use a purpose-built system instead of many full template instances for dense
  fields.
- Bind moving effects to the intended socket or transform and confirm coordinate
  units before tuning offsets.
- On UE 5.7, do not use `-nullrhi` for an integration test that spawns editor
  actors; use the normal RHI. The null-RHI Editor Scripting path can crash before
  Python reports an exception.
- Review stylized effects in grayscale before checking color, density, timing,
  gameplay scale, and attachment. Still images cannot validate motion cadence.

## Require Visual Approval

Before retaining a smoke or fire preset as a baseline:

1. Render a fixed-camera video that includes startup and stable behavior.
2. Record the Niagara/prefab path, sequence, render config, fps, resolution, and
   duration beside the video.
3. Ask the effect owner to review silhouette, color, density, timing, and scale.
4. Keep the result pending until the owner approves it.
5. Retain the exact video and config locally as the regression baseline.

Keep review media outside the repository. Publish approved public assets through
the tracking issue.
