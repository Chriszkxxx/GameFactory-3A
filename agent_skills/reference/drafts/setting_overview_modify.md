# agent_skills - setting overview

This is the mandatory routing overview for AAAGameForge Agents. It identifies
which task-specific Skill and API documents an Agent must read. Detailed task
workflows, schemas, artifact layouts, tests, and implementation rules belong in
the corresponding Skill or API document, not here.

## Document Roles

| Source | Responsibility |
|---|---|
| Task packet | Current task, canonical Engine, inputs, acceptance criteria, and read/write boundaries |
| This overview | Routes the task to the required Skill and API documents |
| Task-specific Skill | Workflow, implementation rules, outputs, provenance, run publication, assembly, tests, and evaluation handoff |
| Engine Context | Public Engine APIs generated engine code may call |
| Browser Serving Context | Public browser session, stream, input, and frontend handoff APIs generated Browser Play code may call |
| Examples | Read-only implementation references used according to the selected Skill |

## Task Router

### Framework And Asset-Generation Development

For model wrappers, Operators, asset Pipeline runners, evaluators, and harness
work, start with:

```text
agent_skills/develop_harness/README.md
```

Then read the matching layer contract:

```text
Model wrapper:
agent_skills/develop_harness/model_require.md

Closed-source API model:
agent_skills/develop_harness/api_model_require.md

Operator:
agent_skills/develop_harness/operatar_require.md

Asset Pipeline runner or evaluator:
agent_skills/develop_harness/pipeline_require.md
```

### Mechanic Generation

For gameplay rules, state, events, commands, runtime adapters, native Mechanic
tests, Mechanic artifact publication, assembly input, or evaluation handoff,
read:

```text
agent_skills/code_gen/mechanic/game_generation.md
agent_skills/engine_context/<canonical_engine>_api.md
```

The Mechanic Skill owns Example/provenance rules, multi-system architecture,
Mechanic/UI separation, `mechanic_contract.json`, run and artifact rules,
manifest hashing, assembly pinning, and verification ownership.

### UI Generation

For engine-native HUDs, widgets, screens, menus, bindings, Browser Play, UI
tests, UI artifact publication, assembly, or evaluation handoff, read:

```text
agent_skills/code_gen/ui/game_ui_generation.md
agent_skills/engine_context/<canonical_engine>_api.md
agent_skills/engine_context/browser_serving_api.md
```

Also read only the finalized Mechanic contract and public adapter paths
declared by the task packet.

The UI Skill owns Native UI and Browser Play delivery, multi-screen
interaction, Mechanic binding, Example/provenance rules, manifests, run and
artifact rules, assembly pinning, screenshots, tests, and verification
ownership. The Browser Serving API owns session, stream, capability, launcher,
and backend/frontend transport contracts.

### Engine Context Selection

The task packet owns the canonical Engine identifier. Select only the matching
API document:

```text
ue5       -> agent_skills/engine_context/ue5_api.md
unity3d   -> agent_skills/engine_context/unity3d_api.md
blender   -> agent_skills/engine_context/blender_api.md
three_js  -> agent_skills/engine_context/three_js_api.md
```

Do not combine APIs or Examples from different Engines.

Browser Serving is selected by delivery target rather than Engine. When the
task includes Browser Play or engine-to-browser presentation, also read:

```text
agent_skills/engine_context/browser_serving_api.md
```

This supplements the selected Engine API; it does not replace it or authorize
mixing APIs from different Engines.

## Reading Order

For a generation task, read:

```text
1. Task packet and acceptance criteria
2. This routing overview
3. The selected Mechanic or UI Skill
4. The matching Engine Context documents
5. Finalized upstream contracts declared by the task packet
6. The minimum relevant Example files allowed by the selected Skill
```

Do not preload unrelated Skills, Engine APIs, Examples, or generated outputs.

## Global Rules

- The task packet is authoritative for task identity, Engine, inputs, and
  filesystem boundaries.
- The selected Skill is authoritative for workflow, required artifacts,
  publication, assembly handoff, validation, and completion criteria.
- Engine Context is authoritative for callable public APIs. Do not invent APIs
  or use adapter internals.
- Examples are read-only references, not base projects, templates, runtime
  dependencies, or limits on what may be generated.
- Read only finalized upstream artifacts explicitly provided to the current
  task. Do not inspect unrelated tasks' generated outputs.
- Record actual context consumption in `context_used.json` when required by the
  selected Skill.
- Generation, assembly, execution, and evaluation have separate ownership and
  status. Source generation alone must not claim that a game is playable.
- Output paths come from `pipeline/common/paths.py`; do not construct repository
  output paths from memory.

## Keep Task Details In Their Skills

Do not add JSON schemas, Example purpose enums, Mechanic systems, UI screen
rules, Browser session fields, artifact layouts, hashing algorithms, assembly
manifests, or evaluation procedures to this overview. Update the owning
Mechanic Skill, UI Skill, framework Skill, or Engine Context document instead.
