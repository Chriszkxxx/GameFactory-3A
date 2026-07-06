# AAAGameForge

**AAAGameForge** is an open framework for AI-driven 3A game content generation and evaluation.

It covers the full production pipeline — 3D assets, scenes, motion, CG video, mechanics, and UI — and doubles as the evaluation harness for 3A game generation.

---

## Directory layout

```
.
├── models/                   # Model wrappers (one file per model)
│   ├── gen_3d_object/        # TRELLIS.2, Hunyuan3D-2.1, TripoSG, ...
│   ├── gen_3d_scene/         # Hunyuan-WorldPlay2, FlashWorld, FantasyWorld
│   ├── gen_motion/           # MoMask, MDM, MLD, T2M-GPT, MotionGPT
│   ├── gen_cg_video/         # LTX, HunyuanVideo, Wan, Mochi, CogVideoX, ...
│   ├── retarget/             # Keemap / IK-based retargeters
│   ├── reasoning/            # LLMs / VLMs (Claude, GPT, Qwen-VL, ...)
│   ├── tools/                # Depth, RMBG, segmentation, ...
│   └── unified_model/        # Composite / multimodal models
│
├── operators/                # Task operators (call models via funcs/)
│   ├── process_input/        # ├── operator.py
│   ├── gen_3d_object/        # ├── funcs/    ← decoupled steps
│   ├── gen_3d_scene/         # └── metrics/  ← per-task evaluation
│   ├── gen_motion/
│   ├── gen_cg_video/
│   ├── retarget/
│   ├── gen_mechanic/
│   └── gen_ui/
│
├── serving/                  # Engine reference code (fed to LLM as context)
│   ├── ue5/ · unity3d/ · common/
│
├── third_party/              # Cloned code-agents (Codex, Claude Code, Aider, …)
│
├── pipeline/                 # Full-chain runners
│   ├── assets_gen/           # Asset generation
│   │   ├── gen_3d_object/    {run.py, eval.py}
│   │   ├── gen_3d_scene/     {run.py, eval.py}
│   │   ├── gen_motion/       {run.py, eval.py}
│   │   ├── gen_cg_video/     {run.py, eval.py}
│   │   └── retarget/         {run.py, eval.py}
│   ├── mechanic/             {run.py, eval.py}  ← mechanic code generation
│   ├── ui/                   {run.py, eval.py}  ← front-end / HUD generation
│   └── full_pipeline/        {run.py, eval.py}  ← end-to-end vertical slice
│
├── test_data/
│   └── test_samples/         # Benchmark test set (per-game + cross-game jsonl)
│       ├── gameA_cyberpunk_shooter/
│       │   ├── general_requirement.txt
│       │   ├── 3D_object/  · 3D_scene/  · motion/  · retarget/
│       │   ├── cg_video/   · mechanic/  · ui/      · pipeline/
│       ├── 3D_object_gen_collect.jsonl    ← cross-game aggregate
│       ├── ...
│       └── pipeline_collect.jsonl
│
├── scripts/installing/
├── test/
└── docs/
```

## Task mapping

| Task              | Model dir             | Operator          | Pipeline runner                        |
|-------------------|-----------------------|-------------------|----------------------------------------|
| 3D object         | `gen_3d_object`       | `gen_3d_object`   | `pipeline/assets_gen/gen_3d_object`    |
| 3D scene          | `gen_3d_scene`        | `gen_3d_scene`    | `pipeline/assets_gen/gen_3d_scene`     |
| Motion            | `gen_motion`          | `gen_motion`      | `pipeline/assets_gen/gen_motion`       |
| CG video          | `gen_cg_video`        | `gen_cg_video`    | `pipeline/assets_gen/gen_cg_video`     |
| Retarget          | `retarget`            | `retarget`        | `pipeline/assets_gen/retarget`         |
| Mechanic          | `reasoning`           | `gen_mechanic`    | `pipeline/mechanic`                    |
| UI                | `reasoning`           | `gen_ui`          | `pipeline/ui`                          |
| Full slice        | (all of the above)    | (all of the above)| `pipeline/full_pipeline`               |

## Status

Skeleton only — directories and empty placeholder files. Implementations to follow.
