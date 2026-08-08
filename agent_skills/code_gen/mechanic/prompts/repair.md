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
Follow the repair workflow and hard boundaries in the referenced Game
Mechanic Generation Skill. Apply the smallest coherent repair to task-owned
Mechanic source and engine-native gameplay test source while preserving the
failed workspace, diagnostics, unrelated working behavior, and packet-defined
contract. Preserve the canonical Engine, public runtime adapter,
`public_api_paths`, and `context_used.json`; update provenance only when the
same registered Context or required Examples are used.

Do not invoke execution or evaluation-only APIs or declare an authoritative
result. Report changed files, addressed failures, and unresolved issues.
