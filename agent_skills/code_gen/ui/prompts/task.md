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

Required Mechanic Examples:

```json
{{MECHANIC_EXAMPLE_PATHS}}
```

Required UI Examples:

```json
{{UI_EXAMPLE_PATHS}}
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
frontend reference from the handoff. Use declared Mechanic bindings only in
the native stage. Do not generate backend source. Browser Play must include a
versioned `browser_play_manifest.json` and a thin launch script that invokes
the public Browser Serving entry point. Generate the packet-defined native/Web
UI source, tests, manifests, fixture, screenshot plan, and provenance.
