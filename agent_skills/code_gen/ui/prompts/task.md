# UI Generation Task

Game UI Generation Skill:

```text
{{UI_GENERATION_SKILL_PATH}}
```

Prepared task packet:

```text
{{TASK_PACKET_PATH}}
```

Workspace:

```text
{{WORKSPACE}}
```

Project and modules:

```text
project={{PROJECT_NAME}}
mechanic={{GAMEPLAY_MODULE_NAME}}
ui={{UI_MODULE_NAME}}
```

Canonical Engine:

```text
{{ENGINE}}
```

Ordered delivery plan:

```json
{{DELIVERY_PLAN}}
```

Existing Engine Context directory:

```text
{{ENGINE_CONTEXT_ROOT}}
```

Mechanic implementation reference roots:

```json
{{MECHANIC_EXAMPLE_ROOTS}}
```

Task-suggested Mechanic reference paths, when present:

```json
{{MECHANIC_EXAMPLE_PATHS}}
```

Native UI implementation reference roots:

```json
{{UI_EXAMPLE_ROOTS}}
```

Task-suggested native UI reference paths, when present:

```json
{{UI_EXAMPLE_PATHS}}
```

Required Browser Play Examples:

```json
{{BROWSER_PLAY_EXAMPLE_PATHS}}
```

Allowed engineering reference purposes:

```json
{{EXAMPLE_REFERENCE_PURPOSES}}
```

Browser Play execution handoff:

```json
{{BROWSER_PLAY_HANDOFF}}
```

Task:

```json
{{TASK_JSON}}
```

General requirement:

```text
{{GENERAL_REQUIREMENT}}
```

Design document:

```text
{{DESIGN_DOCUMENT}}
```

UI requirement:

```text
{{REQUIREMENT}}
```

Acceptance criteria:

```json
{{ACCEPTANCE_CRITERIA}}
```

Finalized Mechanic artifact and contract:

```text
artifact={{MECHANIC_ARTIFACT_PATH}}
contract={{MECHANIC_CONTRACT_PATH}}
```

```json
{{MECHANIC_CONTRACT_JSON}}
```

Mechanic public paths and runtime adapter:

```json
{{MECHANIC_PUBLIC_PATHS}}
```

```json
{{MECHANIC_RUNTIME_ADAPTER}}
```

Resolved native bindings:

```json
{{RESOLVED_BINDINGS}}
```

Screens, constraints, viewports, and forbidden UI:

```json
{{SCREENS}}
```

```json
{{VIEW_CONSTRAINTS}}
```

```json
{{VIEWPORTS}}
```

```json
{{FORBIDDEN_UI}}
```

Reference images:

```json
{{REFERENCE_IMAGE_PATHS}}
```

Required Context usage manifest:

```text
{{CONTEXT_USED_PATH}}
```

Generate `engine_native` first, then generate `browser_play` under
`generated_ui/browser_play/` using the Browser Serving API and repository
frontend reference from the handoff. Inspect the required Browser Play Example
for the complete create-or-recover session and engine-neutral `stream_url`
handoff. Mechanic and native UI Examples are educational code references and
do not restrict the generated game's genre, presentation, or interaction
design. Use declared Mechanic bindings only in the native stage. Do not
generate backend source. Browser Play must include a versioned
`browser_play_manifest.json` and a thin launch script that invokes the public
Browser Serving entry point. Generate the packet-defined native/Web UI source,
tests, manifests, fixture, screenshot plan, and provenance.

Do not scan entire Example roots. Select the smallest set of structural
Mechanic, native UI, and Browser Play reference files needed to learn
plugin/module boundaries, build configuration, public binding patterns,
engine-native UI code, and the Browser handoff. They may come from completely
different game genres. A shooter Example may teach the correct module and
widget architecture for a MOBA, strategy game, simulation, or novel game.

Do not use either Example as a base plugin, inheritance target, visual
template, gameplay template, copied scaffold, or runtime dependency. The
current task requirements and design inputs define the generated UI. Record
only paths actually consulted.

Every `examples_used` entry must include a non-empty `purpose` list selected
from the allowed engineering reference purposes above.

Do not search for an Example with a matching genre, mechanic, HUD, camera, or
visual style. Select any same-Engine reference that teaches engineering
structure and API usage. The absence of a similar Example is never a missing
input or blocker; generate the requested native UI and Browser Play experience
from the task.
