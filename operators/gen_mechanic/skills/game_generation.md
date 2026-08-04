# Game Mechanic Generation

Generate the game-owned mechanic implementation for one task inside the
provided workspace.

## Inputs

Read all provided context before editing:

- the task dictionary and task-specific requirement;
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
4. Consume generated inputs through the descriptors supplied by the Operator.
5. Generate the game-owned extension, configuration, test source, and any
   task-required launch or trace files.
6. Keep behavior deterministic where the requirement needs replay or automated
   verification.
7. Review the generated files against the requirement before returning.

## Hard Boundaries

- Write only inside the allowed workspace.
- Treat task inputs, Engine API References, Skills, and examples as read-only.
- Use only public APIs and public framework contracts documented in the
  selected Engine API Reference.
- Do not import, copy, or modify adapter internals.
- Do not invent generated asset paths or bypass supplied descriptors.
- Do not depend on optional examples, inherit their concrete game classes, or
  make an example a success condition.
- Do not add an example-selection field to the task contract.
- You MUST generate engine-native gameplay test source.
- You MUST NOT invoke Operator/Evaluator-only test execution APIs.
- You MUST NOT declare that the benchmark passed or assign a benchmark score.
- Do not weaken, delete, skip, or replace a failing test merely to make a
  repair appear successful.

## Required Generated Artifacts

Generate only task-owned implementation artifacts:

- engine-native gameplay source;
- engine-native gameplay test source;
- configuration and build files required by the selected engine;
- task-required launch, replay, or trace files.

Do not generate Operator-owned or Evaluator-owned artifacts:

- authoritative build or test reports;
- benchmark scores or evaluator results;
- Operator result metadata.

## Execution Ownership

The Agent generates and repairs game-owned implementation files.

The Operator owns:

- engine project preparation;
- authoritative build execution;
- generated gameplay test execution;
- artifact verification;
- Operator metadata and Repair Prompt assembly.

The Evaluator owns final benchmark execution and scoring.

## Engine Asset Import Handoff

The Agent generates descriptor bindings only. It MUST NOT import assets or
launch the engine.

For execution owned by the Operator, Evaluator, or external execution harness:

1. Prefer the public asset and world operations documented by the selected
   Engine API Reference.
2. Use the readiness signal required by the selected import transport; do not
   block on an unrelated optional control or observation channel.
3. If direct orchestration cannot reliably manage Editor readiness or
   lifecycle, use the repository-provided thin import launcher documented by
   the selected Engine API Reference.
4. A repository import launcher is a wrapper around the public engine adapter;
   it is not an alternate engine API or permission bypass.
5. Continue resolving every input by task descriptor. Do not pass arbitrary
   source asset paths to either the launcher or engine adapter.
6. Preserve structured import results and engine logs as execution evidence.

## Native Environment Readiness

Import success alone does not prove that a native environment is playable.
The execution owner must:

1. Warm the native map until derived data, shaders, textures, and streaming
   work reach a stable state.
2. Inspect real game-window pixels rather than IDE, desktop, log, or splash
   windows.
3. Reject blank, near-white, near-black, severely overexposed, or severely
   underexposed frames even when map-load logs report success.
4. Inspect unresolved lighting, texture-budget, missing-material, missing-map,
   and renderer compatibility warnings.
5. Repair incompatible exposure, lighting, and streaming configuration without
   replacing or visually flattening the supplied environment.
6. Rebuild required lighting or select a documented dynamic-lighting fallback;
   hiding the warning is not a repair.
7. Re-launch after warm-up and capture a stable frame that shows the player
   object, nearby ground, and navigable environment before reporting the game
   as playable.

## Test Integrity

Generated tests support self-check and the Repair Loop. They do not replace
Evaluator-owned benchmark tests.

Tests must:

- exercise behavior observable from the generated game;
- fail when the required mechanic is absent or incorrect;
- cover state transitions and configured values, not only construction;
- avoid unconditional success, empty assertions, and checks of constants that
  do not exercise runtime behavior;
- expose enough diagnostics for a later Repair Prompt.

## Repair

When structured failures are provided:

1. Identify the smallest root cause that explains them.
2. Repair game-owned source and tests without modifying read-only context.
3. Preserve unrelated working behavior and existing failure evidence.
4. Report changed files and unresolved risks.

Return source changes and diagnostics; do not claim execution success.
