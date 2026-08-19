# `agent_skills/asset_qa` — asset generation and visual QA

This directory contains the asset-generation and quality-assurance Skills used
by a vision-capable coding agent. Use it after the game plan identifies an asset
need and before declaring that generated or imported content is ready to ship.

`agent_skills/asset_qa/` covers the parts of asset work that require visual or
runtime judgement: whether a mesh faces the right direction, has plausible
scale, fits the requested style, or produces a usable animation in-game. File
parsing and structural checks alone cannot answer these questions.

## Skill map

| Asset task | Skill | Use it for |
|---|---|---|
| Image preparation and T-pose generation | `agent_skills/asset_qa/image/SKILL.md` | Single-object reconstruction inputs, character T-pose images, alpha preparation, and image QA |
| 3D object generation and review | `agent_skills/asset_qa/3d_object/SKILL.md` | Props, avatars, weapons, mesh quality, provenance, and ship-readiness |
| Imported asset orientation | `agent_skills/asset_qa/3d_object/orientation_review.md` | Forward axis, scale, ground contact, attachment points, and engine import review |
| 3D scene generation | `agent_skills/asset_qa/3d_scene/SKILL.md` | Scene generation or assembly, layout, environment quality, and scene-level review |
| Motion | `agent_skills/asset_qa/motion/SKILL.md` | Rigging, generation/fetch, retargeting, import, and in-game motion review |

Read the selected engine contract from `agent_skills/engine_context/` before
importing an approved asset or scene. The engine documents define formats,
coordinate conventions, public APIs, project structure, and runtime validation.

## Relationship to `agent_skills/code_gen/`

Asset QA and code generation are separate but connected stages:

- `agent_skills/asset_qa/` decides whether planned assets are visually and
  structurally suitable for integration.
- `agent_skills/code_gen/` tells the agent how to turn approved assets into
  gameplay mechanics and UI. Use
  `agent_skills/code_gen/mechanic/game_generation.md` for game behavior and
  `agent_skills/code_gen/ui/game_ui_generation.md` for HUD, menus, and player
  interaction surfaces.
- The selected document under `agent_skills/engine_context/` connects both
  stages to UE5, Blender, Unity, or three.js.

Do not fix an asset's orientation or scale by scattering compensating rotations
inside gameplay code. Record validated asset metadata in the engine’s documented
asset flow, then let the runtime apply it consistently.

## Environment setup map

Use the task-specific installer below before the relevant generation route.
`cloud_api_install.sh` at the `asset_env_setup/` root is the common implementation;
new agent workflows should invoke the task-specific entry point rather than the
shared script directly.

| Asset task | Canonical setup command | Additional setup |
|---|---|---|
| Image / T-pose | No repository-wide installer currently required | See `scripts/asset_env_setup/image/README.md` and `asset_qa/image/SKILL.md` |
| 3D object | `bash scripts/asset_env_setup/3d_object/cloud_api_install.sh` | Local TRELLIS.2: `bash scripts/asset_env_setup/3d_object/trellis2_install.sh` |
| 3D scene | No repository-wide installer currently required | See `scripts/asset_env_setup/3d_scene/README.md` and use the selected engine asset library where appropriate |
| Motion | `bash scripts/asset_env_setup/gen_motion/install.sh` | Then `source scripts/asset_env_setup/gen_motion/runtime_env.sh` |
| Audio | `bash scripts/asset_env_setup/audio/cloud_api_install.sh` | Local checkpoints follow `asset_qa/audio/SKILL.md` |
| CG video | `bash scripts/asset_env_setup/cg_video/cloud_api_install.sh` | Local MiniMax H3: `bash scripts/asset_env_setup/cg_video/minimax_h3_install.sh` |

## Review workflow

1. Start from the approved game plan and its stated style, role, and acceptance
   criteria for the asset.
2. Generate or obtain the asset through the selected route. Prefer reliable
   closed-source/cloud APIs for mature asset types such as 3D objects when
   allowed by cost and privacy constraints. For immature routes such as motion
   or 3D scenes, prefer suitable licensed assets from the selected engine's
   asset library when they provide a better shippable result.
3. Run the task-specific structural checks and the selected Skill’s visual QA.
4. Import the asset using the selected `agent_skills/engine_context/` contract.
5. Run the asset in the target game, exercise relevant player actions, and
   review a low-resolution capture for orientation, attachment, animation,
   clipping, scale, material, VFX, lighting, and style issues.
6. Iterate until the asset meets its planned acceptance criteria. Keep source
   and licence/provenance information with externally sourced assets.

## Where generated results and tests live

- All generated game results belong under `test_data/outputs/`, organized by
  game, run, task kind, and task id. Use `pipeline/common/paths.py`; never
  hand-construct output paths.
- Mechanics and UI belong under each game's run directory, for example
  `test_data/outputs/gameA_cyberpunk_shooter/default/mechanic/<task_id>/` and
  `test_data/outputs/gameA_cyberpunk_shooter/default/ui/<task_id>/`. Do not
  create root-level `test_data/outputs/mechanic/` or `test_data/outputs/ui/`
  directories.
- `test/` contains runnable, current-use test and smoke scripts. Agents should
  use the relevant test to verify that generated assets, game code, or adapter
  flows can actually run; a written file alone is not evidence of success.
- `third_party/` holds externally cloned repositories such as `trimesh` and
  engine material/asset packs. Treat its contents as external dependencies: do
  not modify or redistribute them, and check each upstream licence and setup
  instructions before use.

## Why visual QA is required

The adapter can validate format, hierarchy, triangle count, bounding box, and
animation structure. It cannot determine whether a symmetric mesh faces the
correct way, whether an unseen reconstruction is usable, whether wheel or weapon
attachments are positioned correctly, or whether an animation looks natural.
A vision model or human review of rendered previews and gameplay capture is
therefore required before a visual asset is accepted.

For motion clips, retain the source/licence metadata next to the motion asset
and do not ship non-commercial sources in a product build.
