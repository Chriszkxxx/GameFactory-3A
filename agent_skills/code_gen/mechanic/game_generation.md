# Game Mechanic Generation

Generate the game-owned mechanic implementation for one task inside the
prepared workspace.

## Inputs

Read all provided context before editing:

- the prepared task packet and task-specific requirement;
- the general game requirement, when present;
- acceptance criteria;
- generated asset and motion descriptors;
- the target Engine identifier;
- the read-only Engine Context directory;
- this Skill;
- optional read-only examples.

Task requirements define behavior. Inspect the Engine Context directory and
select exactly one API Reference that matches the target Engine identifier.
That selected document defines the callable engine surface. Examples are
lower-priority implementation references only.

## Workflow

1. Inspect the existing workspace and preserve compatible generated work.
2. Map every acceptance criterion to game-owned source, observable state, and
   at least one meaningful engine-native test.
3. Separate Mechanic requirements from presentation requirements. Convert any
   HUD, widget, menu, screenshot, or visual-feedback wording into required
   state, events, and commands.
4. List the Engine Context directory, identify the API document matching the
   task Engine, and read it before making concrete engine calls.
5. Choose architecture appropriate to the selected engine without extending
   or modifying adapter-owned framework internals.
6. Consume generated inputs through the supplied descriptors.
7. Generate the game-owned extension, configuration, test source, and any
   task-required launch or trace files.
8. Publish `mechanic_contract.json` at the workspace root using schema
   `aaagameforge.mechanic_contract.v1`. It must contain a positive
   `contract_version`, the exact game-owned module name, and non-empty
   `state`, `events`, and `commands` collections.
9. Keep behavior deterministic where the requirement needs replay or automated
   verification.
10. Review the generated files against the requirement before finalization.

## Mechanic And UI Separation

Mechanic generation owns gameplay rules and a presentation-independent
contract. It does not own presentation implementation.

The dependency direction is:

```text
UI -> Mechanic -> runtime framework
```

The reverse dependency is forbidden. Mechanic code must compile, test, and be
evaluated without a UI plugin, HUD, widget, menu, Canvas renderer, or
screenshot.

When requirements contain presentation language, translate it:

```text
"show a health bar"    -> expose current and maximum health state
"show ammo"            -> expose magazine and reserve ammo state
"show victory screen"  -> expose victory state and event
"Restart button"       -> expose a restart command
"pause menu"           -> expose pause/resume state and commands
```

Do not implement the visual element during a Mechanic task.

## Hard Boundaries

- Write only inside the prepared workspace.
- Treat task inputs, Engine Context documents, Skills, Prompts, and examples as
  read-only.
- Do not modify `meta.json`, `demo_outputs/`, or evaluation artifacts.
- Select only the API document matching the task Engine. Do not read concrete
  APIs from unrelated engine documents. Do not mix APIs from multiple engines.
- If no matching non-empty API document exists, report the missing context and
  do not invent an engine API.
- Use only public APIs and public framework contracts documented in the
  selected matching Engine API Reference.
- Do not import, copy, or modify adapter internals.
- Do not invent generated asset paths or bypass supplied descriptors.
- Do not depend on optional examples, inherit their concrete game classes, or
  make an example a success condition.
- Do not create HUD, Widget, Menu, Canvas, UMG, Slate, or SlateCore
  implementation.
- Do not create crosshairs, health bars, ammo displays, telemetry panels,
  layout, styling, visual feedback, or screenshot implementation.
- Do not assign a concrete game HUD from a Mechanic GameMode.
- Do not make the Mechanic module depend on a game UI module.
- UI-facing state must be exposed through the versioned public Mechanic
  contract, not through casts to incidental Pawn, Character, Controller, or
  private implementation types.
- You MUST generate engine-native gameplay test source.
- You MUST NOT invoke execution or evaluation-only test APIs.
- You MUST NOT declare that the benchmark passed or assign a benchmark score.
- Do not weaken, delete, skip, or replace a failing test merely to make a
  repair appear successful.

## Required Generated Artifacts

Generate only task-owned implementation artifacts:

- engine-native gameplay source;
- engine-native gameplay test source;
- `mechanic_contract.json` with versioned state/event/command definitions;
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

## Completion Report

After editing, report:

- files created, modified, or deleted;
- requirement and acceptance-criteria coverage;
- generated gameplay-test coverage;
- unresolved risks or missing inputs.

Do not report an authoritative build, test, or benchmark result.
