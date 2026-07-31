# test_samples/

WorldFlex-GameBenchmark test set — **one directory per game project**, plus
cross-game aggregate jsonls. Read-only input; generated artifacts go to
`../outputs/<game_id>/...` (same first axis — see `../outputs/README.md`).

## Layout

```
test_samples/
├── gameA_cyberpunk_shooter/          ← one directory per game project
│   ├── general_requirement.txt       ← overall spec of the game
│   ├── 3D_object/
│   │   ├── requirement.txt
│   │   ├── ref_images/               ← concept-art references
│   │   └── object_tasks.jsonl        ← one line per 3D-object task
│   ├── tpose/
│   │   ├── requirement.txt
│   │   ├── ref_images/               ← character references
│   │   └── tpose_tasks.jsonl
│   ├── 3D_scene/
│   │   ├── requirement.txt
│   │   ├── ref_images/
│   │   └── scene_tasks.jsonl
│   ├── motion/
│   │   ├── requirement.txt
│   │   ├── ref_videos/
│   │   └── motion_tasks.jsonl
│   ├── retarget/
│   │   ├── source_motions/
│   │   ├── target_skeletons/
│   │   └── retarget_tasks.jsonl
│   ├── cg_video/
│   │   ├── requirement.txt
│   │   └── cg_tasks.jsonl
│   ├── mechanic/
│   │   ├── requirement.txt
│   │   ├── unity_template/           ← or ue5_template/
│   │   └── mechanic_tasks.jsonl
│   ├── ui/
│   │   ├── requirement.txt
│   │   └── ui_tasks.jsonl
│   └── pipeline/
│       ├── design_doc.txt            ← 2-page game-design brief
│       └── pipeline_task.jsonl       ← integrated full-pipeline task
│
├── gameB_fantasy_rpg/                ← (to add)
├── gameC_pokemon_openworld/          ← (to add)
│
└── *_collect.jsonl                   ← cross-game aggregate jsonls
    ├── 3D_object_gen_collect.jsonl
    ├── tpose_gen_collect.jsonl
    ├── 3D_scene_gen_collect.jsonl
    ├── motion_gen_collect.jsonl
    ├── retarget_collect.jsonl
    ├── cg_video_collect.jsonl
    ├── mechanic_collect.jsonl
    ├── ui_collect.jsonl
    └── pipeline_collect.jsonl
```

Directory names and task-list filenames are registered in
`pipeline/common/paths.py` (`TASK_INPUT_DIR`, `TASK_JSONL`, `TASK_COLLECT_JSONL`).
Renaming one here means updating that table.

## Task line schema

Every line in a `*_tasks.jsonl` / `*_collect.jsonl` should carry:

| Field | Purpose |
|-------|---------|
| `game_id` | Which game project this task belongs to → selects the output directory. Inferred from a `test_samples/<game_id>/...` input path when absent, but be explicit. |
| `task_id` | Unique within its `(game_id, task_kind)` → names the output directory. |

Everything else is task-specific (`image_path`, `prompt`, `description`, `seed`, …).
Paths are written **relative to the repo root**.

```jsonc
{"game_id": "gameA_cyberpunk_shooter", "task_id": "cyberpunk_sword_001",
 "image_path": "test_data/test_samples/gameA_cyberpunk_shooter/3D_object/ref_images/cyberpunk_sword.png",
 "prompt": "Stylized cyberpunk energy sword, neon blue glow, game-ready", "seed": 42}
```

A per-game `*_tasks.jsonl` and the cross-game `*_collect.jsonl` hold the same
lines. `run.py --game <id>` prefers the former and falls back to filtering the
latter by `game_id`.

## Current status

Only `gameA_cyberpunk_shooter/` is scaffolded. `3D_object/` and `tpose/` have real
task lines (in the `*_collect.jsonl`); everything else is an empty placeholder.
Populate `requirement.txt` and `*_tasks.jsonl`, then add gameB / gameC.
