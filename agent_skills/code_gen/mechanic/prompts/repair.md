# Mechanic Repair Task

Workspace:

```text
{{WORKSPACE}}
```

Repair attempt:

```text
{{REPAIR_ATTEMPT}} / {{MAX_REPAIR_ATTEMPTS}}
```

Structured execution or evaluation failures:

```json
{{FAILURES_JSON}}
```

Previous finalized result:

```json
{{PREVIOUS_RESULT_JSON}}
```

Use the structured failures and existing workspace to identify the root cause.
Apply the smallest coherent repair to game-owned source and engine-native
gameplay test source.

Requirements:

- preserve the failed project, logs, reports, and unrelated working behavior;
- do not modify read-only references, framework source, task inputs, prepared
  Pipeline files, or examples;
- do not weaken, delete, skip, or replace a failing test to hide a defect;
- preserve the versioned `mechanic_contract.json` state/event/command
  boundary and keep it consistent with engine-native source;
- do not repair a Mechanic failure by adding HUD, Widget, Menu, Canvas, UMG,
  Slate, layout, visual-feedback, or screenshot implementation;
- when a failure mentions a missing visual element, repair the underlying
  Mechanic state, event, or command contract only;
- do not invoke execution or evaluation-only test APIs;
- report changed files, addressed failures, and unresolved issues;
- do not declare build, test, or benchmark success.

The execution or evaluation coordinator will rebuild and rerun tests after the
workspace is finalized.
