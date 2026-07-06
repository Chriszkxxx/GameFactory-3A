# third_party/

Landing area for **cloned code-agent repos** used during benchmark runs, e.g.:

- OpenClaw
- Codex
- Claude Code
- Cline
- Aider
- OpenHands
- Gemini CLI

Each agent should be cloned into its own subdirectory. This folder is **git-ignored
by default** except for this README. If nothing ends up being cloned here, the
directory can be deleted.

## Convention

```
third_party/
├── codex/                  # git clone <upstream>
├── claude-code/
├── aider/
└── ...
```
