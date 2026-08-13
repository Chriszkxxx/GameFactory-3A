# agent_skills — setting overview

Reference context and development guidelines that get injected into an agent's
prompt. Everything here is **prose for an agent to read**, not code to import —
`agent_skills/` deliberately contains no Python.

## What lives here

| Path | Audience | Purpose |
|------|----------|---------|
| `setting_overview.md` | any agent | This file — what `agent_skills/` is and how to navigate it |
| `develop_harness/` | a coding agent extending this repo | Contracts for the `models/` → `operators/` → `pipeline/` asset-generation chain |
| `asset_qa/` | an agent choosing how to generate / QA assets | Per-asset-kind strategy notes (e.g. when to reconstruct a scene vs assemble it) |
| `engine_context/` | the `gen_mechanic` / `gen_ui` code agents | Per-engine API notes (UE5 / Unity3D / Blender / three.js) used when generating engine code |
| `asset_qa/` | a **vision-capable** agent reviewing 3D content | The two questions about an asset that no code can answer: which way it faces, and whether a generated mesh is fit to ship |

```
agent_skills/
├── setting_overview.md            ← start here
├── develop_harness/
│   ├── README.md                  ← workflow (SOP) for adding an asset task
│   ├── model_require.md           ← contract for models/     (one wrapper per model)
│   ├── operatar_require.md        ← contract for operators/  (task dict → artifacts)
│   └── pipeline_require.md        ← contract for pipeline/   (CLI, batching, scoring)
├── engine_context/
│   └── ue5_api.md · unity3d_api.md · blender_api.md · three_js_api.md
└── asset_qa/
    ├── README.md
    ├── imported_asset_orientation.md   ← which way does this model face?
    ├── generated_asset_review.md       ← is this generated mesh shippable?
    └── generate_3D_scene_skills.md ← closed vs open 3D scene strategy
```

## Three different kinds of agent work

The repo has agents on several sides of the fence, and they read different
files:

1. **Developing the framework** — extending the asset-generation chain
   (adding a model wrapper, an operator, a pipeline runner).
   → read `develop_harness/`.

2. **Generating game content** — the Layer-B/C code agents driven by
   `operators/gen_mechanic/` and `operators/gen_ui/`, which write UE5 / Unity3D /
   web code for a target game.
   → read `engine_context/`, plus the reference projects in `engine_adapters/`.

3. **Reviewing generated art** — deciding facing, scale and quality from
   rendered views, then recording the decision through the adapter.
   → read `asset_qa/`.

Don't mix them: `develop_harness/` describes *this repo's* internal conventions;
`engine_context/` describes *external engine* APIs; `asset_qa/` describes
judgements about content, not code.

## Runnable counterparts

The written contracts have an executable counterpart under `test/`, which is where
code belongs:

```bash
pip install pillow numpy scipy          # no GPU, no weights needed

python test/harness/smoke.py            # run every chain with stub models
python test/harness/smoke.py --kind tpose --keep
```

`test/harness/stubs.py` provides fake model wrappers matching the real interfaces,
so a chain can be exercised on a laptop; `smoke.py` asserts that artifacts land at
the paths `pipeline/common/paths.py` promises.

## Ground rules for any agent touching this repo

- **Output paths come from `pipeline/common/paths.py`.** Never concatenate a path
  to `test_data/outputs/` by hand.
- **Dependencies point downward only**: `models/` ← `operators/` ← `pipeline/`.
  A model never imports an operator; an operator never imports a runner.
- **Additive changes to operator return dicts.** Existing keys are consumed by
  `run.py`, `eval.py` and `test/`; removing or repurposing one is a breaking change.
- **New behaviour goes behind a new argument** whose default reproduces the old
  behaviour.
