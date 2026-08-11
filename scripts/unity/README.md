# Unity CLI Scripts

Thin wrappers around `engine_adapters.unity3d.cli` (the `a3game-unity` CLI).

## Commands

### create-project

```bash
scripts/unity/create_project.sh \
    --unity-root /path/to/Unity \
    --project-path /path/to/MyGame \
    --dry-run
```

### import-asset

```bash
scripts/unity/import_asset.sh \
    --unity-root /path/to/Unity \
    --project /path/to/MyGame \
    --game-id my_game \
    --run-id run_001 \
    --task-kind 3d_object \
    --task-id task_001 \
    --artifact-key model_path \
    --type prop \
    --dry-run
```

Asset import accepts repository task identities (game-id/task-id), not
arbitrary source paths. `--artifact-key` is required when the task's
`meta.json` contains more than one non-empty `*_path` field. Remove
`--dry-run` to execute the Unity import. See
`agent_skills/engine_context/unity3d_api.md` for the full contract.

### run

```bash
scripts/unity/run.sh \
    --unity-root /path/to/Unity \
    --project /path/to/MyGame \
    --scene Assets/Scenes/Main.unity \
    --dry-run
```

Remove `--dry-run` to launch the Editor. This one-shot wrapper does not provide
a stop command; programmatic launch/stop must reuse one `UnityClient` instance.

On Windows, use the corresponding `.cmd` files with the same arguments.

## Environment

| Variable | Purpose |
|----------|---------|
| `A3GAME_PYTHON` | Override Python interpreter |

The wrappers require `--unity-root` and `--project`/`--project-path` explicitly.
Runtime host and port are selected with `--runtime-host` and `--runtime-port`.
The broader `UnityClient` Python API can also resolve its documented
`A3GAME_UNITY_*` environment variables when those values are not passed by a
caller.
