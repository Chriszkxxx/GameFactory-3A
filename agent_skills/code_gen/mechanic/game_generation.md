# Game Mechanic Generation

Generate the game-owned mechanic implementation for one task inside the
prepared workspace.

## Inputs

Read all provided context before editing:

- the prepared task packet and task-specific requirement;
- the general game requirement, when present;
- acceptance criteria;
- generated asset and motion descriptors;
- exactly one selected Engine API Reference;
- this Skill;
- optional read-only examples.

Task requirements define behavior. The Engine API Reference defines the
callable engine surface. Examples are lower-priority implementation references
only.

## Workflow

1. Inspect the existing workspace and preserve compatible generated work.
2. Map every acceptance criterion to game-owned source, observable state, and
   at least one meaningful engine-native test.
3. Choose architecture appropriate to the selected engine without extending
   or modifying adapter-owned framework internals.
4. Consume generated inputs through the supplied descriptors.
5. Generate the game-owned extension, configuration, test source, and any
   task-required launch or trace files.
6. Keep behavior deterministic where the requirement needs replay or automated
   verification.
7. Review the generated files against the requirement before finalization.

## Hard Boundaries

- Write only inside the prepared workspace.
- Treat task inputs, Engine API References, Skills, Prompts, and examples as
  read-only.
- Do not modify `meta.json`, `demo_outputs/`, or evaluation artifacts.
- Use only public APIs and public framework contracts documented in the
  selected Engine API Reference.
- Do not import, copy, or modify adapter internals.
- Do not invent generated asset paths or bypass supplied descriptors.
- Do not depend on optional examples, inherit their concrete game classes, or
  make an example a success condition.
- You MUST generate engine-native gameplay test source.
- You MUST NOT invoke execution or evaluation-only test APIs.
- You MUST NOT declare that the benchmark passed or assign a benchmark score.
- Do not weaken, delete, skip, or replace a failing test merely to make a
  repair appear successful.

## Required Generated Artifacts

Generate only task-owned implementation artifacts:

- engine-native gameplay source;
- engine-native gameplay test source;
- configuration and build files required by the selected engine;
- task-required launch, replay, or trace files.

Do not generate Pipeline-owned or Evaluator-owned artifacts:

- prepared task packets or workspace snapshots;
- authoritative build or test reports;
- benchmark scores or evaluator results;
- Pipeline result metadata.

## Execution Ownership

The outer Agent generates and repairs game-owned implementation files.

The Code Generation Pipeline owns:

- deterministic task and context composition;
- Prompt rendering;
- workspace and read-only boundaries;
- prepared task packets and snapshots;
- artifact finalization and metadata.

The execution and evaluation layers own engine preparation, authoritative
builds, generated-test execution, runtime evidence, and benchmark scoring.

## Engine Asset Import Handoff

The outer Agent generates descriptor bindings only. It MUST NOT import assets
or launch the engine.

For later execution:

1. Prefer public asset and world operations documented by the selected Engine
   API Reference.
2. Resolve every input by task descriptor.
3. Reuse one configured Engine client and one ready Engine process session for
   all inputs in the task; do not restart the environment for every asset.
4. Perform readiness checks at the session boundary rather than before every
   individual import.
5. A repository launcher may manage readiness and process lifecycle only when
   the selected API Reference documents it as a wrapper around the same public
   Engine Adapter.
6. Preserve structured import results and engine logs as execution evidence.
7. Do not treat import success or map-load logs as proof that the result is
   playable.

## Test Integrity

Generated tests support self-check and repair. They do not replace
Evaluator-owned benchmark tests.

Tests must:

- exercise behavior observable from the generated game;
- fail when the required mechanic is absent or incorrect;
- cover state transitions and configured values, not only construction;
- avoid unconditional success, empty assertions, and checks of constants that
  do not exercise runtime behavior;
- expose enough diagnostics for a later repair task.

## Repair

When structured failures are provided:

1. Identify the smallest root cause that explains them.
2. Repair game-owned source and tests without modifying read-only context.
3. Preserve unrelated working behavior and existing failure evidence.
4. Report changed files and unresolved risks.

Return source changes and diagnostics; do not claim execution success.
