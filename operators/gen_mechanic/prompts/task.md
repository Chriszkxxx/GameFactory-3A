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

Selected Engine API Reference file:

```text
{{ENGINE_API_REFERENCE_PATH}}
```

Read the selected API file when concrete engine calls are needed. Do not copy
the complete API surface into this prompt or the generated source.

Optional read-only example paths:

```text
{{OPTIONAL_EXAMPLE_PATHS}}
```

Implement the mechanic in the workspace. Generate game-owned engine source and
meaningful engine-native gameplay test source for the acceptance criteria.
Do not execute Operator/Evaluator-only testing APIs and do not declare the
benchmark result.

Use the provided project and game-owned module names. Do not rename them.
Interpret the module as the selected engine's appropriate package, plugin,
module, or equivalent extension unit.

Examples may inform implementation only. The generated project must remain
independent of them.

When the task uses a native environment, generate configuration and launch
artifacts that support execution-owned map warm-up and real-window visual
validation. Do not assume successful import or map-load logs prove that
lighting, exposure, materials, textures, and streaming are visually usable.
