# Mechanic Generation Task

Game Mechanic Generation Skill:

```text
{{GAME_GENERATION_SKILL_PATH}}
```

Prepared task packet:

```text
{{TASK_PACKET_PATH}}
```

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

Target Engine identifier:

```text
{{ENGINE}}
```

Engine Context directory:

```text
{{ENGINE_CONTEXT_PATH}}
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

Optional read-only example paths:

```text
{{OPTIONAL_EXAMPLE_PATHS}}
```

Implement this task inside the workspace under the packet boundaries. Use the
referenced Skill for implementation workflow, Engine API discovery,
Mechanic/UI separation, descriptor consumption, contract publication, and
generated-test requirements.

Use the exact project and game-owned module names above. Produce every
task-required artifact, including the packet-defined
`mechanic_contract.json`. Do not invoke execution or evaluation-only APIs and
do not declare an authoritative result. Report changed files, requirement and
generated-test coverage, and unresolved risks.
