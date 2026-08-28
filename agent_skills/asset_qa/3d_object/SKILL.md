# Generated Asset Review

Judge whether a generated mesh is fit to ship in a browser game, from the
same rendered sheet the orientation review uses.

A generation model optimises for resemblance to one image. A game needs
several other things that no image-to-3D metric measures, and every one
of them is visible in five orthographic views. Run this immediately after
`Gen3DObjectOperator.run_art_plan`, on the sheet at
`result["preview_sheet"]`.

## Choose The Route First

Three routes produce a 3D asset. The cheapest applicable one wins:

| Route | Use when | Cost |
|---|---|---|
| **Spec** (`funcs/code_asset.py`) | the object is exactly describable — a crate, sign, wheel, rifle, railing | seconds, no GPU, no API key |
| **Asset pack** (`funcs/asset_pack.py`) | a CC0 model of it already exists | seconds, one download |
| **Generate** (Tripo / Meshy / TRELLIS.2) | the surface is the point — a face, creature, tree, cloth | paid or GPU-bound, minutes |

`suits_code_asset(subject)` returns `code`, `generate` or `ambiguous`. It
declines rather than guesses: a procedurally "described" face wastes a
correction loop discovering what one call could have said.

For hard-surface work a spec is not a downgrade — it states three things
generation can only guess:

- **facing** (`forward`), so the import records `verified_by="spec"` rather
  than `heuristic`;
- **size** (`height_metres`), where a generated mesh arrives normalised
  into a unit box with no size of its own;
- **parts**, each a named glTF node, so a wheel can still spin. A generated
  mesh is one fused body.

Every route still gets reviewed — skip to *The Five Checks* once a mesh
exists.

### Or Both: Composing Generated Parts

The routes are not exclusive. A `mesh` part reads a GLB off disk — one
component from a cloud model — and is then placed, measured and gated
exactly like a primitive. For a detailed hard-surface asset this is usually
better than either route alone, because the two sides are good at
different things and **the division is not a matter of taste**:

| Delegate to a generator | State as a primitive |
|---|---|
| shapes no formula gives — a grip's finger swells, a stock's cheek weld, stippling | anything with an exact dimension — a receiver, a rail's slot pitch, a barrel's diameters |
| where exact dimensions do not matter | where they are the whole point |

Getting this backwards is the mistake the route makes easy. Generating a
scope for the rifle in `test_data/outputs/gameB_weapon_showcase/` cost
**19,982 triangles** — more than three times the whole rifle's primitive
geometry — for a softened version of a stepped tube that a nine-point
`lathe` profile states exactly. And it cannot afterwards be fixed by
changing a number, which a lathe can.

```python
{"id": "grip", "kind": "mesh",
 "source": "parts/grip.glb",       # required, must exist at validation
 "size": [0.116, 0.116, 0.116],    # write it uniform, see below
 "at": [0, 0.045, -0.104], "rotation": [0, 90, 0],
 "long_axis": "y"}                 # optional; checked against the vertices
```

**`size` is a request, not an extent.** The mesh is fitted by a *single*
factor so it keeps the proportions it was generated with — stretching a
moulded grip to fill a box is a worse defect than a grip 4 mm thinner than
intended. So `size` means "this many metres on your longest axis"; write
one number three times to say so deliberately. `provenance` warns when you
did not, and reports the `actual_extent` to place neighbours against.

**Nothing tells you which way a fetched mesh faces, so measure it.** The
rifle's grip has its flange spanning *x* and its thickness on *z* — a rifle
needs the opposite, so it takes `rotation: [0, 90, 0]`. Rotating about x,
the intuitive reading of "rake it back", tilts the grip in the plane it is
already flat in and it comes out facing across the weapon. Declare
`long_axis` and the `orientation` gate checks the placed geometry against
it.

**A regenerated part is a new set of axes.** Re-fetching that grip textured
produced a file needing `+90` where the previous one needed `-90`. Carrying
a rotation across a regeneration is the mistake `orientation` exists for.

Because of all this, `verified_by` drops to `spec+generated`: the placement
was stated, the mesh inside it was asserted.

### Textures Come Across

A generated part's contribution is mostly *surface* — stippling on a grip,
panel creases and decals on a car shell — and that lives in the atlas, not
the mesh. UVs and the base-colour image are carried into the output, which
is self-contained, and shared between placements: four wheels off one source
cost one copy of the atlas.

Two things to know:

- **Primitives get no UVs.** Giving them arbitrary ones samples an arbitrary
  corner of somebody else's atlas, which is worse than flat colour.
- **Only base colour is taken**, and when the source has a
  metallic-roughness *map* its `metallicFactor`/`roughnessFactor` are
  replaced with dielectric defaults rather than inherited. Those factors are
  left at glTF's default `1.0` to multiply the map, so copying them across
  without it renders a polymer grip as sandblasted steel. Recorded as
  `factors_from: "assumed"`.

**Textured parts are expensive, and `budget` is the gate that says so.** The
first textured grip came back at 12,213 triangles and put the rifle at
22,247 against a weapon budget of 20,000 — refused, correctly. The fix is
not a larger budget: a grip does not need twelve thousand triangles when its
detail is in the atlas. Re-fetch at a lower `decimation_target` and keep the
texture.

### What Generation Will Not Do On Request

A prompt is a request, not a constraint. Asked for a race car body shell
with `NO WHEELS, no tyres, no ground` stated three ways, Meshy returned a
car with wheels — because a car has wheels in everything it has seen.

Plan for that instead of arguing with it: ask for a *part* rather than a
de-featured whole ("one continuous piece of sculpted bodywork with a cockpit
opening"), and keep anything that must be separable as a primitive. For a
car that is not an aesthetic preference — `art_plan` records it as *a car
whose wheels do not turn looks worse than a box that does*, and a fused
wheel cannot turn at any quality.

## Building From A Spec

```python
op = Gen3DObjectOperator(model=None, run_id="20260826_1400")   # no model needed
result = op.run({
    "game_id": "gameA_cyberpunk_shooter",
    "task_id": "crate_001",
    "asset_id": "supply_crate",
    "spec": {
        "subject": "wooden supply crate",
        "units": "metres",          # required, no default
        "forward": "+z",            # required, no default
        "asset_type": "prop",
        "height_metres": 0.6,
        "materials": {"wood": {"baseColor": [0.45, 0.30, 0.18, 1],
                               "roughness": 0.85}},
        "parts": [
            {"id": "body", "kind": "box",
             "size": [0.6, 0.6, 0.6], "at": [0, 0.3, 0], "material": "wood"},
        ],
    },
})
```

`units` and `forward` have no defaults, because an assumed facing is the
defect `orientation_review.md` exists to catch: it reads as correct until
the asset is in a scene walking backwards.

Part kinds: `box`, `cylinder`, `cone`, `sphere`, `torus`, `lathe`,
`extrude`, `mesh`. `lathe` revolves a `(radius, height)` profile — bottles,
blades, turned legs; `extrude` pushes a closed `(x, y)` outline along Z;
`mesh` reads a GLB (see *Or Both*). `segments` is the triangle-budget dial
on round parts, and `chamfer` (0–0.5, a fraction of the half-extent) cuts a
box's edges back — a sharp edge catches light as one hard line, which is
what makes a box read as a toy brick.

**A `lathe` profile must start and end at radius 0.** Otherwise the revolved
surface is a pipe with open ends: no interior, and a hole you see through
once something is behind it. Refused at validation, because unlike a
proportion there is no version of this that was intended. Profiles may be
traced in either direction — the writer normalises by signed area, so there
is no winding rule to remember.

### Gates, Run Before Any Renderer

Eight checks run on the spec's own geometry, so a defect is found on points
rather than after a render. All report together, so one pass gives the
whole list.

| Gate | Catches | Blocks? |
|---|---|---|
| `solidity` | a part thin enough to vanish edge-on | yes |
| `chirality` | a `-l`/`-r` pair that is a rotation, not a mirror | yes |
| `scale` | parts disagreeing with `height_metres`, or a misplaced decimal | yes |
| `budget` | more triangles than the role allows | yes |
| `connectivity` | a part touching nothing else | no — reported |
| `provenance` | what was delegated to a generator, and at what cost | only if it is really a generated asset |
| `orientation` | a fetched part whose long axis is not where it was declared | no — reported |
| `windings` | an inside-out or unclosed part | yes for a primitive, reported for a fetched mesh |

**Chirality is the one to understand**, because its failure looks tidy.
Negating *two* axes is a 180-degree rotation, and rotation preserves
handedness — both halves come out as the same hand. Measured in
[img2threejs](https://github.com/img2threejs/img2threejs): z `+0.288` against
`-0.288`, where a mirror leaves z alone. **Negate the lateral axis only.** Any
left/right pair — headlights, wing mirrors, sling swivels — is one sign error
from this.

**`windings` is the only gate that evaluates the mesh**, and it exists
because four primitives once shipped inside-out while every other gate
passed them: the GLB was valid, the counts matched, the bounds were right,
and a viewer that does not cull backfaces shades an inverted solid
identically. It would have appeared first inside an engine. Review a mesh
with backface culling **on**, for the same reason.

`connectivity` only reports: a hovering crystal is a design, and failing it
would make the gate wrong for a whole class of asset. `provenance` mostly
reports too — it fails only when the composition is *mostly* generated
parts *and* triangles, at which point it is a generated asset with
primitives attached and should go through an orientation review rather than
inherit a spec's label. An unclosed *fetched* mesh is likewise reported and
not failed: no spec edit repairs it, and a gate that blocks work nobody can
fix gets bypassed.

A failed gate writes **nothing** and hands nothing to the engine — an asset
that exists gets used. `strict=False` only to inspect a bad mesh.

### Correcting A Spec

Pass `revise(spec, failures) -> spec` to let a model fix its own defects.
The loop stops at three attempts, or earlier on `repeating`, `oscillating`,
`no_progress` or `revise_failed`; `result["stop_reason"]` says which. An
unbounded loop in [img2threejs](https://github.com/img2threejs/img2threejs)
spent 45 minutes recording a car that never moved, because a lookup returned
`None` and the loop optimised a metric that could not see it.

**Read `stop_reason` before re-running.** `repeating` means the revision
addressed nothing, so a fourth attempt is the third attempt.

## Environment setup

A spec needs no environment at all — pure standard library, no GPU, no
key. Set up only the generation route you actually chose:

```bash
# Cloud 3D backends such as Tripo and Meshy
bash scripts/asset_env_setup/3d_object/cloud_api_install.sh

# Optional local TRELLIS.2 runtime
bash scripts/asset_env_setup/3d_object/trellis2_install.sh
```

Use only the selected route. Keep API keys in environment variables and large
local checkpoints outside source control or under `<REPO_PATH>/third_party/`.

**Prefer the cloud APIs — Tripo, then Meshy** — over local TRELLIS.2; they are
the more reliable route for game-ready meshes. They are paid, so before the first
call **pause and follow *Paid cloud backend* in
`<REPO_PATH>/agent_skills/asset_qa/README.md`**: recommend the provider, send the
purchase/API-key page (<https://platform.tripo3d.ai/api-keys> or
<https://www.meshy.ai/api>), state the estimated cost for the planned mesh count
including regeneration attempts, ask the user to buy access and supply
`TRIPO_API_KEY` / `MESHY_API_KEY`, and wait for an explicit answer. Use local
TRELLIS.2 only when the user declines or requires offline execution.

## Which Formats Each Engine Accepts

Read from each adapter's own importer, so this is what will actually load:

| Engine | Accepted mesh formats |
|---|---|
| UE5 | `fbx` `glb` `gltf` `obj` `usd` `usda` `usdz` |
| Blender | `abc` `fbx` `glb` `gltf` `obj` `ply` `usd` `usda` `usdc` `usdz` |
| Unity | `fbx` `glb` `gltf` `obj` |
| three.js | `glb` `gltf` |

**glTF is the intersection, so target `.glb`.** Every route here already
does. The one consequence worth knowing: three.js accepts *only* glTF, so an
FBX from a cloud backend needs converting before it reaches a browser game,
while the same file imports into UE5 or Unity untouched.

Prefer `.glb` over `.gltf` — a single binary file cannot arrive with its
`.bin` or its textures missing.

## The Five Checks

**1. Is it the right thing?** Compare the sheet against the concept image
saved beside the mesh (`concept.png`) and against the plan's prompt. A
"treasure chest" that reconstructed as a rounded lump is a concept-image
failure, not a mesh failure: regenerate the image, not the mesh.

**2. Does the back exist?** Single-image reconstruction invents whatever
the photograph did not show. The `-z` view — the side away from the input
camera — is where that invention lives. Flat, smeared, or hollow backs
are acceptable for something the player only sees from the front (a
building facade, a wall-mounted prop) and disqualifying for anything they
walk around.

**3. Is it upright and complete?** The `+y` view says whether the subject
stands. A cropped concept image reconstructs as a truncated mesh — legs
ending at the ankle, a tree with no crown — because the geometry simply
stops where the image did. Regenerate; nothing downstream can repair it.

**4. Is there a floor under it?** Look at the `+y` view for a pale sheet
around the subject, and at the side views for a thin dashed line at its
base. Image-to-3D crops its input to the subject's own silhouette, so a
standing figure touches the frame edge and the model frequently infers a
ground plane — measured at a fifth of the triangle budget, and a 2.4 m
grey pancake once the asset is scaled to a character's height.

`<REPO_PATH>/operators/gen_3d_object` removes this automatically
(`funcs/mesh_cleanup.py`) and reports what it took out. A **solid slab**
in the review sheet means the removal was refused, which it does whenever
the diagnosis would cost more than 40% of the mesh — check the task's
`ground_plate` report for the reason before assuming a bug. Sparse specks
at floor level are the floor's rubble and are harmless.

Spec-built assets skip this check: a spec cannot invent a floor, and running
the removal on one risks deleting a plinth that was asked for.

**5. Is it inside its budget?** The sheet title states the triangle count.
The budgets live in `BUDGET_BY_ROLE` in
`<REPO_PATH>/operators/gen_3d_object/funcs/art_plan.py`, keyed by role rather than
asset type, because what matters is how *often* a thing is drawn:

| Role | Triangles | Texture |
|---|---|---|
| `avatar` — hero character, seen close | 40 000 | 2048 |
| `weapon` — held, small on screen | 20 000 | 1024 |
| `prop` — interacted with, one or two per scene | 20 000 | 1024 |
| `scenery` — repeated dozens of times | 8 000 | 1024 |
| `landmark` — seen once, at a distance | 20 000 | 1024 |

A repeated tree at 200 000 triangles costs more than the whole rest of the
scene. Set `role` on the plan entry and **regenerate**: a triangle budget
cannot be fixed afterwards, because decimating a textured mesh outside the
generator throws its UVs away, and TRELLIS.2 bakes the texture *after* it
decimates. Never decimate a finished asset by eye.

**6. Is the scale plausible?** The title states the composed bounding box.
Generated meshes arrive normalised into a unit box, so this number is
meaningless in isolation — what matters is that the plan's `height` is a
real height for that subject. A chair at 3 m and a doorway at 1.6 m are
the two failures that make a scene read as a toy.

## Recording The Outcome

- **Accept**: run the orientation review
  (`<REPO_PATH>/agent_skills/asset_qa/3d_object/orientation_review.md`) and
  record the facing axis. An accepted asset with an unverified facing is not
  finished. A spec-built asset carries its facing as data, so the review
  confirms rather than establishes it.
- **Regenerate**: change the plan entry — prompt, seed, `role`,
  `triangles`, `texture` — and say which, so the next run is a different
  attempt rather than the same one.
- **Switch route**: a generated mesh that fails twice on something a spec
  states outright — scale, facing, parts that need to move — is telling you
  the subject was describable. Write the spec instead of buying a third
  generation.
- **Reject**: keep the primitive fallback. This is a real answer. A
  bevelled primitive with honest materials and a fitted shadow looks
  better than a melted mesh, and `assets.instantiateOrBuild` already
  falls back to it with no code change.

## What Generation Does Not Fix

Reach for the framework before reaching for the GPU. In descending order
of visible effect per line of code, a generated three.js scene is decided
by `host.setEnvironment({ preset })`, filmic tone mapping, a fitted
shadow camera, bevelled edges, honest materials, and contact shadows —
all of them documented in
`<REPO_PATH>/agent_skills/engine_context/three_js_api.md`. An unlit scene full of
generated art still looks like an unlit scene; a lit scene full of
primitives does not.

Generation is also the wrong tool for anything that must **articulate**.
A generated mesh is one fused body: a car's wheels cannot spin, a chest's
lid cannot open, a character cannot be skinned. Either generate the shell
and keep the moving parts as primitives driven by gameplay — which is what
`entity.visual` is for — or build the whole thing from a spec, where every
part is already a named node.
