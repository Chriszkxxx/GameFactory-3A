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
│   ├── gen_mechanic/         # code-gen agent system:
│   │   ├── agent/            #   ├── agent/    ← wraps a code agent (Claude Code / Codex)
│   │   ├── prompts/          #   ├── prompts/  ← system + task prompt templates
│   │   └── skills/           #   └── skills/   ← agent-callable engine skills
│   └── gen_ui/               # same agent/ · prompts/ · skills/ layout
│
├── serving/                  # Engine reference code (fed to LLM as context)
│   ├── ue5/ · unity3d/ · common/    ← implemented in a separate repo, to be migrated
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
│   ├── test_samples/         # Benchmark test set (per-game + cross-game jsonl)
│   │   ├── gameA_cyberpunk_shooter/
│   │   │   ├── general_requirement.txt
│   │   │   ├── 3D_object/  · 3D_scene/  · motion/  · retarget/
│   │   │   ├── cg_video/   · mechanic/  · ui/      · pipeline/
│   │   ├── 3D_object_gen_collect.jsonl    ← cross-game aggregate
│   │   ├── ...
│   │   └── pipeline_collect.jsonl
│   └── outputs/              # Single fixed output root (all evals read from here)
│       ├── mechanic/<game>__<taskid>/   # generated engine project + demo_outputs + launch.sh
│       ├── ui/<game>__<taskid>/
│       └── eval_result/<game>__<taskid>/ # build.log · judge_log.json · reward.txt
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

## Code generation (Layer B/C) — agent system

Unlike asset operators (single `model.infer()` call), **code generation** (`gen_mechanic`,
`gen_ui`) is a multi-turn agent loop and lives under the operator as a self-contained
agent system, inspired by [GameCraft-Bench](https://github.com/FreedomIntelligence/gamecraft-bench):

- `operators/<task>/agent/`   — wraps a code agent (Claude Code / Codex); injects context, retries/repairs on build failure
- `operators/<task>/prompts/` — system + task prompt templates
- `operators/<task>/skills/`  — agent-callable skills teaching engine build / headless-launch / screenshot / replay
- `serving/`                  — engine reference projects (UE5 / Unity3D) fed to the agent as context

`pipeline/mechanic/run.py` organizes the requirement → assembles context (spec + serving + skills)
→ launches the code agent (interactive dialog for debug, or non-interactive for benchmark)
→ writes the generated project to `outputs/`. `eval.py` then runs the verifier
(build_check gate → trace replay → hidden-rubric multimodal judge).

## Outputs — single fixed root

All artifacts land under one fixed root (`test_data/outputs/`) so any eval (asset /
code / full pipeline) reads from the same place, right next to the test set:

```
test_data/outputs/
├── mechanic/<game>__<taskid>/     # generated engine project + demo_outputs/*.json + launch.sh
├── ui/<game>__<taskid>/
├── 3d_object/<taskid>.glb         # asset outputs also land here
└── eval_result/<game>__<taskid>/  # build.log · judge_log.json · reward.txt
```

## Status

Skeleton only — directories and empty placeholder files. Implementations to follow.
