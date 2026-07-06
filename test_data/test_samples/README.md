# test_samples/

WorldFlex-GameBenchmark test set. See `../../_cache_code/WorldFlex-GameBenchmark.md`.

## Layout

```
test_samples/
├── gameA_cyberpunk_shooter/          ← one directory per game project
│   ├── general_requirement.txt       ← overall spec of the game
│   ├── 3D_object/
│   │   ├── requirement.txt
│   │   ├── ref_images/               ← concept-art references
│   │   └── object_tasks.jsonl        ← one line per 3D-object task
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
    ├── 3D_scene_gen_collect.jsonl
    ├── motion_gen_collect.jsonl
    ├── retarget_collect.jsonl
    ├── cg_video_collect.jsonl
    ├── mechanic_collect.jsonl
    ├── ui_collect.jsonl
    └── pipeline_collect.jsonl
```

## Current status

Only `gameA_cyberpunk_shooter/` scaffold exists (all files empty).
Populate `requirement.txt` and `*_tasks.jsonl` files, then add gameB / gameC.
