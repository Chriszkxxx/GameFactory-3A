# Code Generation Migration Notes

This document records the implemented outer-Agent code-generation layout for
review. Existing README and Agent navigation documents are intentionally left
unchanged pending maintainer approval.

## Implemented Ownership

- `agent_skills/code_gen/` contains read-only Skills and Prompt templates.
- `agent_skills/engine_context/` contains callable Engine API references.
- `pipeline/common/` contains reusable task-neutral workspace preparation and
  finalization helpers.
- `pipeline/code_gen/gen_mechanic/run.py` composes one Mechanic task and
  explicit API Reference for direct outer-Agent edits.
- `pipeline/code_gen/gen_mechanic/eval.py` remains a separate existing-artifact
  evaluation entry point.

The canonical Code Generation Pipeline must not load a Model, construct an
Operator, call `model.run()`, launch a nested Agent, or select a concrete
Engine implicitly.

## Implemented Execution

```text
run.py prepare
    -> task + Skill + Prompt + explicit API Reference
    -> prepared workspace
    -> outer Agent edits task-owned source
    -> run.py finalize
    -> preserved source artifact
```

Shared `pipeline/common/prepare.py` and `finalize.py` are intended for both
Mechanic and future UI generation.

## Removed Legacy Paths

The completed Mechanic migration removes:

- `operators/gen_mechanic`
- `pipeline/mechanic`
- nested `CodexAgent`, `StubAgent`, and `model.run` execution;
- legacy Mechanic Agent/Operator tests.

Mechanic behavior is now covered by `test/test_code_gen_mechanic.py`.
