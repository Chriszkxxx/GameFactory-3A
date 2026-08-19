# Generated Asset Review

Judge whether a generated mesh is fit to ship in a browser game, from the
same rendered sheet the orientation review uses.

A generation model optimises for resemblance to one image. A game needs
several other things that no image-to-3D metric measures, and every one
of them is visible in five orthographic views. Run this immediately after
`Gen3DObjectOperator.run_art_plan`, on the sheet at
`result["preview_sheet"]`.

## Environment setup

Choose the environment based on the 3D generation backend:

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
  finished.
- **Regenerate**: change the plan entry — prompt, seed, `role`,
  `triangles`, `texture` — and say which, so the next run is a different
  attempt rather than the same one.
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
lid cannot open, a character cannot be skinned. Generate the shell, keep
the moving parts as primitives driven by gameplay, and swap only the
visual — which is what `entity.visual` exists for.
