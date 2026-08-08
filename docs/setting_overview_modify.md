# agent_skills - setting overview

Reference context and development guidelines that get injected into an
Agent's prompt. Everything here is prose for an Agent to read, not code to
import. `agent_skills/` deliberately contains no Python.

## What Lives Here

| Path | Audience | Purpose |
|------|----------|---------|
| `setting_overview.md` | any Agent | Mandatory navigation entry point |
| `develop_harness/` | framework development Agent | Contracts for the `models/` -> `operators/` -> `pipeline/` asset-generation chain |
| `code_gen/mechanic/` | Mechanic generation Agent | Mechanic workflow, boundaries, Prompts, tests, contract, and provenance rules |
| `code_gen/ui/` | UI generation Agent | Engine-native UI and Browser Play frontend workflow |
| `engine_context/` | Mechanic/UI generation Agents | Callable Engine and Browser Serving API references |

```text
agent_skills/
|-- setting_overview.md
|-- develop_harness/
|   |-- README.md
|   |-- model_require.md
|   |-- operatar_require.md
|   `-- pipeline_require.md
|-- code_gen/
|   |-- mechanic/
|   `-- ui/
`-- engine_context/
    |-- ue5_api.md
    |-- unity3d_api.md
    |-- blender_api.md
    |-- three_js_api.md
    `-- browser_serving_api.md
```

## Two Different Kinds Of Agent Work

The repository has Agents on both sides of the framework boundary.

1. **Developing the framework** - extend the asset-generation chain by adding
   a model wrapper, Operator, Pipeline runner, Engine adapter, or Browser
   Serving backend.
   Read `develop_harness/` and the relevant framework source.

2. **Generating game content** - execute Layer-B/C generation through
   `pipeline/code_gen/gen_mechanic/` or `pipeline/code_gen/gen_ui/`.
   Read the corresponding `code_gen/` Skill, the applicable API documents in
   `engine_context/`, and the Engine-owned Examples under `engine_adapters/`.

Do not mix these responsibilities. `develop_harness/` describes this
repository's framework conventions. `engine_context/` describes public APIs
that generated game code may call.

## Engine API Context Rules

- The Pipeline task owns the canonical Engine identifier. The Agent must not
  change it.
- All callable Engine API references must be discovered under
  `agent_skills/engine_context/`.
- Mechanic generation must read the API document matching the selected Engine
  before generating Engine calls.
- UI generation must read both:
  - the API document matching the selected Engine; and
  - `agent_skills/engine_context/browser_serving_api.md`.
- Do not mix Engine APIs or Examples from different Engines.
- Record every API and required Example used in `context_used.json`.
- Engine-to-Browser backends are framework-owned and must be registered before
  normal UI generation.
- UI generation may create a task-owned Browser Play frontend under the
  current workspace path `generated_ui/browser_play/`. The canonical published
  run artifact path is `artifacts/ui/<task_id>/browser_play/`.
- Browser Play may use the Browser Serving API, but it must not generate or
  modify an `EngineBackend` or write `generated_adapters/`.

## Generation Run And Output Contract

### Run Is The Atomic Unit

One generation run is the smallest published and reproducible unit:

```text
Task Packet
    |
    v
Generation Run
    |
    v
Artifacts
    |
    v
Assembly
    |
    v
Playable Product
    |
    v
Evaluation
```

All generated inputs, artifacts, products, and evaluation evidence belonging
to one attempt must live under:

```text
test_data/outputs/<game_id>/runs/<run_id>/
```

Published runs are immutable:

- do not overwrite an artifact in a published run;
- do not repair a published run in place;
- create a new run for a content-affecting repair;
- record the previous run through `parent_run_id`, `repair_of`, and the failure
  digest;
- keep unpublished Agent retries under `_pipeline/attempts/`;
- promote only the selected attempt into the run's published artifacts.

Example repair lineage:

```json
{
  "run_id": "run_002",
  "parent_run_id": "run_001",
  "trigger": "repair",
  "repair_of": {
    "run_id": "run_001",
    "failure_digest": "sha256:..."
  }
}
```

### Canonical Run Layout

```text
test_data/outputs/
`-- <game_id>/
    `-- runs/
        `-- <run_id>/
            |-- run.json
            |-- inputs.lock.json
            |-- artifacts/
            |   |-- assets/
            |   |   `-- <task_kind>/<task_id>/
            |   |-- mechanic/
            |   |   `-- <task_id>/
            |   |       |-- native/
            |   |       |-- contract/
            |   |       |-- tests/
            |   |       |-- traces/
            |   |       |-- context_used.json
            |   |       `-- manifest.json
            |   `-- ui/
            |       `-- <task_id>/
            |           |-- native/
            |           |-- browser_play/
            |           |-- bindings/
            |           |-- fixtures/
            |           |-- tests/
            |           |-- screenshot_plan.json
            |           |-- context_used.json
            |           `-- manifest.json
            |-- products/
            |   `-- <pipeline_task_id>/
            |       |-- native/
            |       |-- browser_play/
            |       |-- launch/
            |       |-- assembly_manifest.json
            |       `-- product_manifest.json
            |-- evaluation/
            |   `-- <pipeline_task_id>/
            |       |-- build/
            |       |-- tests/
            |       |-- screenshots/
            |       |-- browser_smoke/
            |       |-- logs/
            |       `-- result.json
            `-- _pipeline/
                |-- packets/
                |-- attempts/
                |-- prompts/
                `-- snapshots/
```

`pipeline/common/paths.py` owns the construction of every path in this layout.
Agents and framework modules must not assemble these paths manually.

### Engine-Neutral Native Artifacts

Use `native/`, not `plugin/` or `native_plugin/`, as the cross-engine artifact
boundary. `native/` means the implementation owned by the selected Engine.

Examples:

```text
Unreal:
native/Plugins/GameUI/

Unity:
native/Assets/UI/

Three.js:
native/src/components/
```

The same rule applies to Mechanic artifacts:

```text
Unreal:
artifacts/mechanic/<task_id>/native/Plugins/GameMechanic/

Unity:
artifacts/mechanic/<task_id>/native/Assets/Mechanics/

Three.js:
artifacts/mechanic/<task_id>/native/src/mechanics/
```

Upper Pipeline layers must not assume that an Engine-native artifact is an
Unreal Plugin.

### Artifact And Product Ownership

- `artifacts/mechanic/<task_id>/native/` is the Mechanic implementation source
  of truth.
- `artifacts/ui/<task_id>/native/` is the Engine-native UI source of truth.
- `artifacts/ui/<task_id>/browser_play/` is the game-owned Browser Play source
  of truth.
- `products/<pipeline_task_id>/` is an assembled, self-contained product.
- Files copied into a product are read-only assembly outputs, not new source
  locations.
- A source artifact change requires a new assembly and new product digest.
- Framework-owned Browser Serving code remains under
  `engine_adapters/browser_serving/` and is never copied into a game artifact.
- `Binaries/`, `Intermediate/`, `Saved/`, Derived Data Cache, `__pycache__/`,
  and other mutable build output belong under `.tmp`, not published runs.

### Versioned And Hashed Manifests

Every published task artifact must include `manifest.json`. A path alone is not
sufficient provenance. The manifest must identify both the artifact format and
the exact content:

```json
{
  "schema_version": "aaagameforge.artifact_manifest.v1",
  "artifact_version": 1,
  "identity": {
    "game_id": "gameC_dwarven_ruins_exploration",
    "run_id": "run_002",
    "task_kind": "mechanic",
    "task_id": "dwarven_exploration_core_001"
  },
  "artifact": {
    "path": "artifacts/mechanic/dwarven_exploration_core_001/native",
    "tree_sha256": "...",
    "file_count": 18
  },
  "producer": {
    "git_sha": "...",
    "packet_sha256": "..."
  }
}
```

Keep version meanings separate:

- `schema_version` identifies the manifest schema;
- `artifact_version` identifies the artifact contract revision;
- `contract_version` identifies a public Mechanic or UI contract revision;
- `tree_sha256` identifies the exact artifact bytes.

Directory artifacts use a deterministic tree hash. Compute it from sorted
POSIX-relative paths, each file's SHA256, and each file's byte size. Exclude
the manifest itself and mutable build/cache output.

All manifest paths are relative to the run root. Do not publish machine-local
absolute paths such as `D:\Desktop\...`.

### Assembly And Evaluation Pin Exact Inputs

An assembly manifest must record the exact manifest and content digests of
every consumed artifact:

```json
{
  "schema_version": "aaagameforge.assembly_manifest.v1",
  "inputs": [
    {
      "role": "mechanic",
      "manifest": "artifacts/mechanic/core_001/manifest.json",
      "manifest_sha256": "...",
      "tree_sha256": "..."
    },
    {
      "role": "ui",
      "manifest": "artifacts/ui/ui_001/manifest.json",
      "manifest_sha256": "...",
      "tree_sha256": "..."
    }
  ]
}
```

Assembly must recalculate each digest and fail on any mismatch. It must never
silently assemble an artifact that changed after its manifest was written.

Evaluation must pin the product it validates:

```json
{
  "subject": {
    "product_manifest": "products/vertical_slice_001/product_manifest.json",
    "product_manifest_sha256": "..."
  }
}
```

Build results, screenshots, runtime logs, and Browser Play smoke evidence are
valid only for that pinned product digest.

### Generation, Assembly, And Verification Status

Do not use one ambiguous `completed` status for all stages. Track at least:

```json
{
  "generation_status": "generated",
  "assembly_status": "assembled",
  "verification_status": "not_run"
}
```

Only a Pipeline execution stage may set `verification_status` to `verified`.
Static source generation or artifact-presence checks must not claim that a
game is playable.

## Runnable Counterparts

The written contracts have executable counterparts under `test/`, which is
where code belongs:

```bash
pip install pillow numpy scipy

python test/harness/smoke.py
python test/harness/smoke.py --kind tpose --keep
```

`test/harness/stubs.py` provides fake model wrappers matching the real
interfaces, so a chain can be exercised without production model weights.
`smoke.py` asserts that artifacts land at the paths promised by
`pipeline/common/paths.py`.

## Ground Rules For Any Agent Touching This Repository

- Output paths come from `pipeline/common/paths.py`. Never concatenate a path
  to `test_data/outputs/` by hand.
- Dependencies point downward only: `models/` <- `operators/` <- `pipeline/`.
  A model never imports an Operator; an Operator never imports a runner.
- Changes to Operator return dictionaries are additive. Existing keys are
  consumed by `run.py`, `eval.py`, and tests.
- Put new behavior behind a new argument whose default preserves existing
  behavior.
- Treat task inputs, Skills, Prompts, API Context, Examples, and finalized
  upstream artifacts as read-only during generation.
- Do not modify README files. Keep architecture plans, changed-file
  inventories, and validation reports under `docs/`.
