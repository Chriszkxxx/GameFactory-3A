# Existing character + garment fitting

`code_asset.fit_wearable_asset` and `code_asset_templates.fit_wearable` expose the
same optional Blender worker. They accept rigged FBX/GLB characters and static
FBX/GLB garments, keeping the garment's triangles, UVs and material slots.
The ordinary `build_code_asset` and rigid armour template paths remain available.
Run the following example from the repository root. Replace the relative asset
paths and Blender Python environment with your local configuration.

```python
from operators.gen_3d_object.funcs.code_asset import fit_wearable_asset

result = fit_wearable_asset(
    body="test_data/inputs/character.fbx",
    clothing="test_data/inputs/garment.glb",
    output="test_data/outputs/wearable/character_clothed.glb",
    coverage="full_body",       # use upper_body for a jacket/shirt
    sleeve_pose="down",         # source sleeves: down, a, or t
    height_metres=1.75,
    clearance_metres=0.008,
    headwear_offset_metres=0.0,  # adjust only when the garment includes headwear
    blender_python=".venv-blender/bin/python",
)
print(result["glb_path"], result["report_path"])
```

The worker requires `bpy` (tested with Blender 4.2) and `numpy`. It runs in its
own process with Python's isolated import mode. `BLENDER_PYTHON` can supply the
executable instead. The library does not search for or install environments.
On hosts where the bpy wheel needs extra shared libraries, set the runtime's
`LD_LIBRARY_PATH` before invoking the caller.

The body must have one humanoid armature. Mixamo names and common variants such
as `LeftUpperArm`/`LeftLowerArm`, `LeftUpLeg`/`LeftThigh`, and `LeftToeBase` are
recognized. Head, hips, arms, forearms, hands, upper/lower legs, feet and toes
establish the frame and anatomical anchors. An unrigged body fails explicitly.

The fit uses these stages:

1. Establish body up/forward from bones and feet, then normalize standing height.
   A character whose wingspan is its longest dimension still gets the requested
   **vertical** height.
2. Align garment anatomical heights. A shirt's hem maps to the hip, not the floor.
   The body's arms temporarily match the garment's source sleeve pose.
3. Separate sleeve influence from the vest/torso along the mesh surface. Same
   positions across UV seams share the distance field. This keeps low cuffs on
   the arms and stops nearby vest flaps or trousers inheriting hand weights.
4. Match sleeve shoulder/elbow/wrist segments, expand cross sections against the
   body while retaining garment layers, and correct nearby intersections.
   Transfer barycentrically interpolated weights from the appropriate body
   region, normalize to four influences, then inverse-skin into the body rest pose.
5. Correct residual intersections in the rest pose and export the shared rig.

`source_heights` overrides the source garment's anatomical heights, expressed as
fractions of its own vertical span. Defaults are an initial fitting guide, not
semantic detections. Full-body defaults are ankle `.05`, knee `.27`, hip `.49`,
waist `.60`, shoulder `.81`, neck `.88`; upper-body defaults are hip `.01`, waist
`.20`, shoulder `.82`, neck `.97`. Values must increase in this order. Use these
controls for unusually long coats, exaggerated armour or cropped tops.
`clothing_rotation=(x, y, z)` supplies XYZ degrees in Blender's Z-up frame for a
misoriented garment. It does not guess the source facing from its bounding box.

Outputs are `.glb`, `.fit.json`, and (unless `save_blend=False`) `.blend`. The
source assets are never edited. The GLB contains the character's rest skeleton
and garment skin; source animation clips are not copied. The report records
source/target heights, vertex/material counts, bone groups, inverse-skin error,
local surface clearance statistics, and actual Blender skin checks in A/down
poses. `headwear_offset_metres` optionally lifts the headwear above the neck
without moving the collar; leave it at zero for an outfit without a hat.

Inspect the collar, cuffs, loose accessories and animation poses. Nearest-surface
clearance is evaluated within 8% of character height and is not a global triangle
intersection proof or cloth simulation. It does not detect garment self-collision
or add runtime collision handling. Separate rigid plates can continue using
`armour_fit.fit_armour`; continuous deformation may bend rigid plate shapes.

Rigid composition example and spec checks (these do not exercise the Blender worker):

```sh
python test/test_3d_object_compose.py
python test/test_3d_object_spec.py
```

### Garments with shoes

Use `footwear_mode="replace"` only for full-body garments with closed shoes
and cuffs covering the ankles. The worker cuts original body geometry below
the ankle plus 2% of body height from the output. It excludes those feet from
collision fitting but keeps the uncut body as the skin-weight donor, so the
garment shoes are not pushed apart by a second pair of boots. The default
`preserve` keeps the original feet. This is an explicit coverage declaration,
not automatic shoe segmentation; open sandals and short cuffs need a separate
mask. Source assets are unchanged. Inspect ankle seams in the intended motion.
