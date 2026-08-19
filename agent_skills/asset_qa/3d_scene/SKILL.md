# Generate 3D Scene — Strategy Skill

Choose how to build a `3d_scene` asset from the scene type. Do not default to one
pipeline for every task: closed rooms and open outdoor worlds need different
geometry strategies.

## Decision

| Scene type | Prefer | Why |
|---|---|---|
| Closed / indoor / bounded (rooms, corridors, arenas with walls) | WorldPlay-style reconstruction | One reference image can become multi-view footage, then a coherent scene mesh |
| Open / outdoor / unbounded (fields, roads, city blocks, terrain) | Base plane or terrain + place objects | Horizon and sky break depth-to-mesh; composition from ground + props is more controllable |

If the task packet does not say which kind it is, infer from the reference image
and requirement text: visible enclosing walls and a finite volume → closed;
ground that extends to the horizon or an open sky → open.

## Closed scenes — WorldPlay / point-cloud → mesh

Use when the playable space is enclosed and most of the geometry should come
from one visual reference.

Typical chain in this repo:

1. Reference image (+ optional prompt / camera pose) → WorldPlay video frames
2. Frames → WorldMirror depth / point cloud
3. Point cloud → continuous mesh (`<REPO_PATH>/operators/gen_3d_scene`, sky cull + tangent-plane faces)
4. Export GLB / PLY under the `3d_scene` output path

When to use this path:

- Interior rooms, caves, tunnels, small arenas with clear walls/ceiling
- The reference already shows the layout the player should inhabit
- You need a single fused scene mesh rather than separately authored props

Watch-outs:

- Occlusion boundaries and sky/background still need the meshing guards in
  `gen_3d_scene` (sky segmentation, tangent-plane continuity, normal-agreement cull)
- Do not expect clean infinite outdoor horizons from this path

Entry points: `<REPO_PATH>/pipeline/assets_gen/gen_3d_scene/{run,eval,render}.py`,
`<REPO_PATH>/test/test_3D_scene_gen.py`.

## Open scenes — plane / terrain + objects

Use when the world is large, mostly ground-driven, or meant to be assembled from
reusable assets.

Recommended strategy:

1. Load or generate a base surface — flat plane, heightmap terrain, or a simple
   road/ground kit mesh
2. Generate or select individual objects with `gen_3d_object` (buildings, props,
   characters, vehicles)
3. Place those objects on the base surface according to the task layout
   (spawn points, lanes, cover, landmarks)
4. Keep the scene as a composed assembly (ground + instances), not one baked
   WorldPlay mesh of the whole horizon

When to use this path:

- Outdoor maps, racing circuits, open battlefields, city blocks with sky
- Layout is defined by gameplay (lanes, spawn areas) more than by one photo
- You need editable / swappable props rather than a single reconstructed shell

Watch-outs:

- Do not feed a wide outdoor reference into WorldPlay and expect a clean
  continuous mesh to the horizon — depth stretching and sky curtains are common
- Prefer explicit ground + object placement over trying to “fix” open-world
  reconstruction with post-filters alone

## Quick checklist

1. Classify: closed vs open (from task text / reference).
2. Closed → WorldPlay / WorldMirror mesh path.
3. Open → base plane or terrain, then place `gen_3d_object` (or kit) assets.
4. Write artifacts to the paths `<REPO_PATH>/pipeline/common/paths.py` defines for `3d_scene`.
5. Visually check continuity (closed) or placement / scale on ground (open)
   before accepting the asset.
