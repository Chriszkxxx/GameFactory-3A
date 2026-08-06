# Code Generation Migration Notes

This document records the implemented outer-Agent code-generation layout for
review. Existing README and Agent navigation documents are intentionally left
unchanged pending maintainer approval.

## Implemented Ownership

- `agent_skills/code_gen/` contains read-only Skills and Prompt templates.
- `agent_skills/engine_context/` contains callable Engine API references.
- `pipeline/common/` contains reusable task-neutral workspace preparation and
  finalization helpers.
- `pipeline/code_gen/gen_mechanic/run.py` currently composes one Mechanic task
  for direct outer-Agent edits. The Pipeline provides the Engine identifier and
  Engine Context directory; the Agent selects the matching API document.
- `pipeline/code_gen/gen_mechanic/eval.py` remains a separate existing-artifact
  evaluation entry point.

The canonical Code Generation Pipeline must not load a Model, construct an
Operator, call `model.run()`, launch a nested Agent, or select a concrete
Engine implicitly.

## Implemented Execution

```text
run.py prepare
    -> task + Skill + Prompt + Engine Context root
    -> prepared workspace
    -> outer Agent edits task-owned source
    -> run.py finalize
    -> preserved source artifact
```

Shared `pipeline/common/prepare.py` and `finalize.py` provide the current
task-neutral lifecycle. The next refactor will add
`pipeline/common/code_gen.py` for reusable parsing and boundary helpers.

## Removed Legacy Paths

The completed Mechanic migration removes:

- `operators/gen_mechanic`
- `pipeline/mechanic`
- nested `CodexAgent`, `StubAgent`, and `model.run` execution;
- legacy Mechanic Agent/Operator tests.

Focused Mechanic CodeGen tests are not present on the current `ue` branch.
Adding behavior-locking tests is Phase 0 of
`docs/mechanic_pipeline_decomposition_plan.md`.

## Next Refactor

The current Mechanic runner combines too many responsibilities. The approved
decomposition and new-conversation handoff are recorded in:

```text
docs/mechanic_pipeline_decomposition_plan.md
```
