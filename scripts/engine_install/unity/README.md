# Unity CLI Scripts

Thin wrappers around `engine_adapters.unity3d.cli` (the `a3game-unity` CLI).

## Project Path Contract

The Agent owns project selection. It must pass the exact Unity project root
produced by the pipeline, for example:

```text
test_data/outputs/<game_id>/<run_id>/pipeline/<task_id>/unity_project/<ProjectName>
```

`<ProjectName>` is the directory that directly contains `Assets/`, `Packages/`,
and `ProjectSettings/`. Do not pass `pipeline/`, `unity_project/`, or the
project's `Assets/` directory. The scripts do not discover, guess, join, or
rewrite this path, and they do not copy source assets themselves. All asset
and generated-code inputs must be canonical benchmark descriptors resolved by
`UnityClient`.

For a complete run, use the same project path for every command and keep one
Editor lifecycle:

```text
Agent selects generated project root
        -> UnityClient/project.create (only for a new empty project)
        -> UnityClient/runtime.launch_editor(project root)
        -> UnityClient.generate_game (one GenerateGame job)
        -> UnityClient runtime/session/observe
```

Prefer `generate-game` for a full game. Use `import-batch` only for an asset
import-only operation. Do not invoke `import-asset` once per asset when a
batch can be submitted; that would create separate Editor jobs and can start
separate Unity licensing processes. The scripts are command launchers only;
the public `UnityClient` and the Unity Editor own project creation, importing,
compilation, build, Play Mode, and runtime behavior.

## Commands

### generate-game

For a complete generated game, provide one JSON job containing canonical
output descriptors and the generated scene specification:

```bash
scripts/engine_install/unity/generate_game.sh \
    --unity-root /path/to/Unity \
    --project /path/to/generated/pipeline/fps_pipeline_001/unity_project/MyGame \
    --job-file /path/to/generated_game.json
```

`UnityClient.generate_game()` writes a project-local manifest under
`Library/A3GameForge/jobs/`. One Unity Editor session then performs the
Unity-native operations in order: install finalized mechanic/UI assemblies,
import avatars/weapons/motions/scenes through `AssetDatabase`, compose the
scene, refresh and compile scripts, run `BuildPipeline`, and optionally enter
Play Mode. This avoids launching one Unity process per stage.

The job must use descriptors that resolve through canonical
`test_data/outputs/<game_id>/<run_id>/...` metadata. Raw paths from
`test_samples` or `asset/` are not accepted by the public client.

### create-project

```bash
scripts/engine_install/unity/create_project.sh \
    --unity-root /path/to/Unity \
    --project-path /path/to/generated/pipeline/fps_pipeline_001/unity_project/MyGame \
    --dry-run
```

### import-asset

```bash
scripts/engine_install/unity/import_asset.sh \
    --unity-root /path/to/Unity \
    --project /path/to/generated/pipeline/fps_pipeline_001/unity_project/MyGame \
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
scripts/engine_install/unity/run.sh \
    --unity-root /path/to/Unity \
    --project /path/to/generated/pipeline/fps_pipeline_001/unity_project/MyGame \
    --scene Assets/Scenes/Main.unity \
    --dry-run
```

Remove `--dry-run` to launch the Editor. This one-shot wrapper does not provide
a stop command; programmatic launch/stop must reuse one `UnityClient` instance.

### import-batch

To import all prepared assets with one Unity Editor startup, create a JSON
array of canonical descriptors (the same fields accepted by `import-asset`):

```json
[
  {"game_id":"gameB_fps_test","run_id":"run_001","task_kind":"3d_object","task_id":"player_char","asset_type":"avatar"},
  {"game_id":"gameB_fps_test","run_id":"run_001","task_kind":"motion","task_id":"jogging","asset_type":"motion","skeleton":"Assets/Generated/Prefabs/player_char.prefab"}
]
```

Then run:

```bash
scripts/engine_install/unity/import_asset.sh import-batch \
    --unity-root /path/to/Unity \
    --project /path/to/generated/pipeline/fps_pipeline_001/unity_project/MyGame \
    --batch-file /path/to/assets.json
```

The client resolves every descriptor first, orders avatars/meshes before
motions and scenes, runs `ImportBatch.RunFromCLI` once, and returns one report
per task. The shell wrapper remains a thin command launcher.

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
