# test_data/

```
test_data/
├── test_samples/   ← read-only task inputs, one directory per game project
└── outputs/        ← generated artifacts, same `<game_id>` first axis
```

## Status

`test_samples/` provides the **basic test structure** only — the directory
layout, the task-list filenames, and the `*_tasks.jsonl` / `*_collect.jsonl`
line schema (see [`test_samples/README.md`](test_samples/README.md)). We do
**not** ship a complete, ready-to-run test case input yet: most
`requirement.txt` and `*_tasks.jsonl` files under
`test_samples/gameA_cyberpunk_shooter/` are still empty placeholders.

## You do not need a prepared test case

The Skills are complete. Hand a coding agent
`<REPO_PATH>/agent_skills/setting_overview.md` together with your game
requirement — in **any format** (a sentence, a bullet list, a design doc, a
reference image folder) — and the agent produces good results on its own: it
reads the entry-point skill, routes itself to the right asset skill and engine
API context, and calls the pipelines.

```text
1. Open a coding agent, such as Codex, Claude Code, or another compatible agent.
2. cd <REPO_PATH>
3. Give the agent your game requirement and ask it to read
   agent_skills/setting_overview.md first.
```

Use `test_samples/` when you want a fixed, reproducible input for pipeline-level
runs and regression comparison; use the agent path for actually generating a
game.
