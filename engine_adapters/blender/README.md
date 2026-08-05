# engine_adapters/blender

Blender (`bpy`) reference code — asset import, rig / retarget, headless preview,
and a playable session.

> Blender is not a fourth target engine. It is the neutral step between a
> generator and one: the only adapter here that reads `.ply` and `.usd`, that can
> re-pivot or decimate an asset the generator got wrong, and that can render a
> picture of the result — or let you walk around it — without a project, a
> licence or a GPU.

## Files

| Path | Runs where | Purpose |
|------|-----------|---------|
| `import_generated/import_mesh.py` | a `bpy` interpreter | import → condition → measure → re-export → report |
| `render_preview.py` | a `bpy` interpreter | turntable / still render of an asset, headless |
| `runtime/` | a `bpy` interpreter | a live session driven by JSON over UDP — spawn, move, effects, snapshot |
| `rig_io.py` | a `bpy` interpreter | Puppeteer rig `.txt` + GLB → armature with skin weights |
| `world_delta.py` | a `bpy` interpreter | world-delta motion retarget → animated FBX for UE |
| `mappings/` | a `bpy` interpreter | bone-map generation, skeleton dumps, known-good presets |
| `../../scripts/import_generated_asset.py` | host Python | finds Blender, launches the importer, reads the report |
| `../../scripts/prepare_world_asset.py` | host Python | world export → one continuous `.glb` (needs no Blender) |

Everything except `runtime/` is batch: a file in, a file out, the process exits.
`runtime/` is the other mode — one long-lived process holding a scene that
commands mutate — and it is the answer to questions a report cannot settle, like
whether a repaired world can actually be walked through. See its own README.

## Running

Two interpreters can run everything here, and the code does not care which:

```bash
# a Blender application
blender --background --factory-startup \
    --python engine_adapters/blender/import_generated/import_mesh.py -- \
    --src out/model.glb --dest library/ --name Sword_001 --preview

# or a Python that has the wheel
pip install bpy==4.2.0
python engine_adapters/blender/import_generated/import_mesh.py \
    --src out/model.glb --dest library/ --name Sword_001 --preview
```

`blender --python x.py -- ...` hands the *whole* command line to the script, so
everything after the bare `--` is the script's. Under the pip wheel there is no
separator; `_script_argv()` handles both.

The host-side launcher finds either one for you and speaks the same
`--usage / --pivot / --target-tris` vocabulary as the UE5 and Unity routes:

```bash
python scripts/import_generated_asset.py --engine blender \
    --src test_data/outputs/<game>/<run>/assets/3d_object/<task>/model.glb \
    --blender-preview
```

## Units and axes

Blender is metres and **Z-up**; glTF is metres and **Y-up**; UE is centimetres
and Z-up. The glTF importer and exporter convert in both directions, so a round
trip `glb → Blender → glb` is identity — which is what makes Blender safe to put
between a generator and UE5. The FBX exporter is set to `-Z` forward / `Y` up for
the same reason.

The `.ply` importer applies **no** conversion, because a PLY has no axis
metadata to convert from. `scripts/prepare_world_asset.py --up z` is where a
Z-up world export gets rotated, once, before anything else sees it.

## Rig and retarget

Reference implementation of the Puppeteer chain: a rig `.txt` (joints, hierarchy,
skin weights) plus its textured GLB become a Blender armature, and a source
animation is retargeted onto it by world-space rotation delta:

```
delta_ws  = src_pose_ws @ src_rest_ws⁻¹
target_ws = delta_ws @ dst_rest_ws
```

Transferring world rotations rather than local ones makes the result independent
of the destination bone's roll, which is what removes the arm drift and backward
knees that local-frame retargeting produces. It also means the source can be a
Mixamo FBX or a MoMask BVH interchangeably — the importer is picked by extension
and the root bones come from the mapping JSON.

```bash
python -m engine_adapters.blender.world_delta \
    --glb char.glb --rig char.txt --source-anim motion.bvh \
    --mapping engine_adapters/blender/mappings/presets/momask_bvh_to_puppeteer_mapping.json \
    --output out.fbx --fps 20
```

Run these as **package modules** (`python -m engine_adapters.blender...`); they
import each other relatively.

No mapping for a new source skeleton? Generate one from topology instead of
writing bone names by hand:

```bash
python -m engine_adapters.blender.mappings.generate_mapping_auto \
    --glb char.glb --rig char.txt --source-anim motion.bvh \
    --output mappings/my_mapping.json
```

## Headless rendering

The pip `bpy` wheel drives EEVEE and Workbench through a GL/EGL context. A
machine without a display has none, and the failure is a `libEGL` abort rather
than an exception, so `render_preview.py` defaults to **Cycles on CPU** and falls
back to it when a GL engine is asked for and dies. Grease-pencil objects go
through GL even under Cycles and take the process down uncatchably; they are
hidden from the render and restored afterwards.

```bash
blender --background --factory-startup \
    --python engine_adapters/blender/render_preview.py -- \
    --src world.glb --out previews/ --mode orbit --format mp4
```

`--format mp4` needs an FFMPEG writer, which the Blender application bundles and
**the pip wheel does not** — under the wheel the `file_format` enum has no
`FFMPEG` entry at all. `auto` and `mp4` both fall back to a PNG sequence and
record why, so a turntable still comes out either way.

Output paths are made absolute before they reach `bpy`. Blender resolves a
relative render path against the blend file, and headless there is none: the
render then writes nothing and still reports `FINISHED`. For the same reason
every report field naming a file is filled in only after that file is confirmed
on disk.

## Dependencies

| Module | Needs |
|--------|-------|
| `import_generated/import_mesh.py`, `render_preview.py` | `bpy` only |
| `runtime/` | `bpy` only — and `runtime/send_command.py` needs nothing at all |
| `rig_io.py`, `world_delta.py`, `mappings/` | `bpy`, `numpy`, `trimesh` |

Every `bpy` import is deferred in the two importer modules, so the host-side
launcher and `test/` can read their constants with no Blender installed.

## Verified

Run against **Blender 5.0.1** (pip `bpy` wheel, Python 3.11, no display, no GPU):

- the importer and the preview renderer — see `import_generated/README.md` for
  the measured numbers and how to reproduce them;
- the playable runtime — `runtime/selftest.py`, 17/17 steps and 5/5 effect
  backends, plus a live server driven over UDP from a Python with no Blender in
  it. `runtime/README.md` records two Blender 5.0.1 findings that cost real time
  to diagnose.

The host side — job files, argument shapes, tier defaults — is covered by
`test/test_world_asset.py`, which needs no Blender.

Not executed here: `rig_io.py`, `world_delta.py` and `mappings/`, which need a
rigged character and a source animation rather than a synthetic fixture.
