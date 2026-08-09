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

Existing Engine Context directory:

```text
{{ENGINE_CONTEXT_ROOT}}
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

Engine-validated Mechanic reference roots:

```json
{{MECHANIC_EXAMPLE_ROOTS}}
```

Task-suggested reference paths, when present:

```json
{{MECHANIC_EXAMPLE_PATHS}}
```

Allowed engineering reference purposes:

```json
{{EXAMPLE_REFERENCE_PURPOSES}}
```

Required Context usage manifest:

```text
{{CONTEXT_USED_PATH}}
```

Implement this task inside the workspace under the packet boundaries. Use the
referenced Skill for implementation workflow, Engine API discovery,
Mechanic/UI separation, reference inspection, descriptor consumption, contract
publication, provenance recording, and generated-test requirements.

Do not scan or read the entire Mechanic reference root. Select the smallest set
of files needed to understand how this Engine expresses a game-owned plugin or
module, build configuration, public runtime adapter, and native tests in code.
The reference may come from a completely different genre or mechanic. For
example, a shooter plugin may teach the correct Engine plugin architecture for
a strategy, simulation, MOBA, or entirely novel game.

These files are educational engineering references only. They are not a base
implementation, gameplay template, inheritance target, scaffold to copy, or
runtime dependency.

Derive all gameplay behavior and architecture from the current task. You may
implement mechanics, classes, systems, and code organization that do not exist
in any Example. Record only the reference paths actually consulted in
`context_used.json`.

Every `examples_used` entry must include a non-empty `purpose` list selected
from the allowed engineering reference purposes above. Use purposes to state
why the file was read, not what gameplay it contains.

Do not classify the task into an Example category or search for a matching
genre, mechanic, camera, control scheme, or game loop. Choose any same-Engine
reference that demonstrates the engineering pattern you need to learn. The
absence of a similar Example is never a missing input, blocker, or reason to
reduce the requested game.

Use the exact project and game-owned module names above. Produce every
task-required artifact, including the packet-defined
`mechanic_contract.json`, public runtime adapter, and `context_used.json`.
Do not invoke execution or evaluation-only APIs and do not declare an
authoritative result. Report changed files, requirement and generated-test
coverage, and unresolved risks.
