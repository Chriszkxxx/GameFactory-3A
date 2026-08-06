# Mechanic Generation Task

Workspace:

```text
{{WORKSPACE}}
```

Project name:

```text
{{PROJECT_NAME}}
```

Game-owned module name:

```text
{{GAMEPLAY_MODULE_NAME}}
```

Game Mechanic Generation Skill file:

```text
{{GAME_GENERATION_SKILL_PATH}}
```

Prepared task packet:

```text
{{TASK_PACKET_PATH}}
```

Task:

```json
{{TASK_JSON}}
```

General requirement:

```text
{{GENERAL_REQUIREMENT}}
```

Task-specific requirement:

```text
{{REQUIREMENT}}
```

Acceptance criteria:

```json
{{ACCEPTANCE_CRITERIA}}
```

Generated asset descriptors:

```json
{{ASSET_SOURCES}}
```

Generated motion descriptors:

```json
{{MOTION_SOURCES}}
```

Target Engine identifier:

```text
{{ENGINE}}
```

Engine Context directory:

```text
{{ENGINE_CONTEXT_PATH}}
```

List this directory and select exactly one API document matching the target
Engine identifier. Read that document before making concrete engine calls.
Do not mix APIs from other engine documents, and do not copy the complete API
surface into this Prompt or the generated source.

Optional read-only example paths:

```text
{{OPTIONAL_EXAMPLE_PATHS}}
```

Implement the Mechanic in the workspace. Generate game-owned engine source and
meaningful engine-native gameplay test source for the acceptance criteria.
Do not execute evaluation-only APIs and do not declare the benchmark result.

Generate Mechanic implementation only. If the general requirement,
task-specific requirement, or acceptance criteria mention HUDs, widgets,
menus, visual feedback, screenshots, health bars, ammo displays, victory
screens, or buttons, convert those statements into required public Mechanic
state, events, and commands. Do not implement their presentation.

Create `mechanic_contract.json` at the workspace root using schema
`aaagameforge.mechanic_contract.v1`. Set `gameplay_module` to
`{{GAMEPLAY_MODULE_NAME}}` and define non-empty versioned `state`, `events`,
and `commands` collections. Keep the engine-native contract consistent with
that artifact.

The Mechanic must compile and its gameplay tests must run without any game UI
plugin, HUD, Widget, Menu, Canvas, UMG, Slate, visual layout, or screenshots.
Do not assign a concrete game HUD from the Mechanic GameMode.

Use the provided project and game-owned module names. Do not rename them.
Interpret the module as the selected engine's appropriate package, plugin,
module, or equivalent extension unit.

Examples may inform implementation only. The generated project must remain
independent of them.
