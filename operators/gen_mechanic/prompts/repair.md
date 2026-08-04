# Mechanic Repair Task

Workspace:

```text
{{WORKSPACE}}
```

Repair attempt:

```text
{{REPAIR_ATTEMPT}} / {{MAX_REPAIR_ATTEMPTS}}
```

Structured Operator failures:

```json
{{FAILURES_JSON}}
```

Previous Agent result:

```json
{{PREVIOUS_AGENT_RESULT_JSON}}
```

Use the structured failures and existing workspace to identify the root cause.
Apply the smallest coherent repair to game-owned source and engine-native
gameplay test source.

Requirements:

- preserve the failed project, logs, reports, and unrelated working behavior;
- do not modify read-only references, framework source, task inputs, or
  examples;
- do not weaken, delete, skip, or replace a failing test to hide a defect;
- do not invoke Operator/Evaluator-only test execution APIs;
- report changed files, addressed failures, and unresolved issues;
- do not declare build, test, or benchmark success.

The Operator will rebuild and rerun tests after this response.
