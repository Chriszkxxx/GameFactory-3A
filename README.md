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
├── engine_adapters/          # Engine reference code (fed to LLM as context)
│   ├── ue5/ · unity3d/ · blender/ · three_js/   ← implemented in a separate repo, to be migrated
│
├── agent_skills/             # Reference context + guidelines for agents (docs only)
│   ├── setting_overview.md   #   start here — what lives where
│   ├── develop_harness/      #   contracts for the models/ · operators/ · pipeline/ chain
│   └── engine_context/       #   per-engine API notes fed to code-gen agents
│
├── third_party/              # Cloned code-agents (Codex, Claude Code, Aider, …)
│
├── pipeline/                 # Full-chain runners
│   ├── common/paths.py       # ← single source of truth for every input/output path
│   ├── assets_gen/           # Asset generation
│   │   ├── gen_3d_object/    {run.py, eval.py}
│   │   ├── gen_tpose_image/  {run.py, eval.py}
│   │   ├── gen_3d_scene/     {run.py, eval.py}
│   │   ├── gen_motion/       {run.py, eval.py}
│   │   ├── gen_cg_video/     {run.py, eval.py}
│   │   └── retarget/         {run.py, eval.py}
│   ├── mechanic/             {run.py, eval.py}  ← mechanic code generation
│   ├── ui/                   {run.py, eval.py}  ← front-end / HUD generation
│   └── full_pipeline/        {run.py, eval.py}  ← end-to-end vertical slice
│
├── test_data/
│   ├── test_samples/         # Benchmark test set — one dir per game project
│   │   ├── gameA_cyberpunk_shooter/
│   │   │   ├── general_requirement.txt
│   │   │   ├── 3D_object/  · tpose/    · 3D_scene/  · motion/  · retarget/
│   │   │   ├── cg_video/   · mechanic/ · ui/        · pipeline/
│   │   ├── 3D_object_gen_collect.jsonl    ← cross-game aggregate
│   │   ├── ...
│   │   └── pipeline_collect.jsonl
│   └── outputs/              # Single fixed output root — mirrors test_samples/
│       └── <game_id>/<run_id>/
│           ├── assets/{3d_object,tpose,3d_scene,motion,cg_video,retarget}/<task_id>/
│           ├── mechanic/<task_id>/ · ui/<task_id>/ · pipeline/<task_id>/
│           └── eval/<task_kind>/<task_id>/
│
├── scripts/installing/
├── test/                     # Integration tests + test/harness/ (stub models, CPU smoke test)
└── docs/
```

## Task mapping

| Task              | Model dir             | Operator          | Pipeline runner                        |
|-------------------|-----------------------|-------------------|----------------------------------------|
| 3D object         | `gen_3d_object`       | `gen_3d_object`   | `pipeline/assets_gen/gen_3d_object`    |
| T-pose image      | `gen_image`           | `gen_tpose_image` | `pipeline/assets_gen/gen_tpose_image`  |
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
- `engine_adapters/`          — engine reference projects (UE5 / Unity3D) fed to the agent as context

`pipeline/mechanic/run.py` organizes the requirement → assembles context (spec + engine_adapters + skills)
→ launches the code agent (interactive dialog for debug, or non-interactive for benchmark)
→ writes the generated project into that game's run directory. `eval.py` then runs the verifier
(build_check gate → trace replay → hidden-rubric multimodal judge).

## Outputs — one directory per generated game project

All artifacts land under one fixed root (`test_data/outputs/`), right next to the
test set, organized **per game project** so the output tree mirrors
`test_samples/`. An artifact is uniquely addressed by
`(game_id, run_id, task_kind, task_id)`:

```
test_data/outputs/
└── gameA_cyberpunk_shooter/               # one dir per game project
    ├── latest -> default/                 # symlink to the most recent run
    └── <run_id>/                          # "default", or a timestamp via `--run-id auto`
        ├── run_meta.json                  # ckpts · seeds · git sha · argv
        ├── assets/
        │   ├── 3d_object/<task_id>/       # model.glb · meta.json
        │   ├── tpose/<task_id>/           # tpose_fg.png · tpose.png · meta.json
        │   └── {3d_scene,motion,cg_video,retarget}/<task_id>/
        ├── mechanic/<task_id>/            # engine project · demo_outputs/*.json · launch.sh
        ├── ui/<task_id>/                  # UI code · screenshots/
        ├── pipeline/<task_id>/            # end-to-end vertical slice
        └── eval/
            ├── <task_kind>/<task_id>/     # metrics.json · build.log · judge_log.json · reward.txt
            └── summary.json
```

Never hand-build these paths — always go through `pipeline/common/paths.py`:

```python
from pipeline.common import paths
out_dir = paths.task_output_dir("gameA_cyberpunk_shooter", "3d_object", "cyberpunk_sword_001")
```

Relocate the whole tree without touching code:
`export AAAGF_OUTPUT_ROOT=/data/scratch/aaagf_outputs`.
See `test_data/outputs/README.md` for the full rationale, and
`--out-dir` for the legacy flat-output escape hatch.

## Running

```bash
# every task of every game, into <game>/default/
python pipeline/assets_gen/gen_3d_object/run.py

# one game project, into a fresh timestamped run dir
python pipeline/assets_gen/gen_3d_object/run.py --game gameA_cyberpunk_shooter --run-id auto
```

## Developing a new asset-generation link

`agent_skills/develop_harness/` holds the contracts for the three layers; the
runnable counterpart lives in `test/harness/` and needs no GPU. Read
`develop_harness/README.md` first, then:

```bash
pip install pillow numpy scipy    # the harness needs nothing else

python test/harness/smoke.py                 # run every chain with stub models
python test/harness/smoke.py --kind tpose --keep
```

| Doc | Layer |
|-----|-------|
| `develop_harness/model_require.md` | `models/` — one wrapper per model |
| `develop_harness/operatar_require.md` | `operators/` — task dict → artifacts |
| `develop_harness/pipeline_require.md` | `pipeline/` — CLI, batching, scoring |

## Status

Skeleton — `gen_3d_object` and `gen_tpose_image` are implemented end to end;
the remaining tasks are directories and empty placeholder files.

