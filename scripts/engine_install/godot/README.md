# Godot 4 setup and launchers

Install a Godot 4 editor build from the
[official download](https://godotengine.org/download/) and put `godot4` or
`godot` on `PATH`, or set `A3GAME_GODOT_EXECUTABLE` to the executable.
`A3GAME_GODOT`, then legacy `AAAGF_GODOT`, are executable-path fallbacks. Set
`A3GAME_GODOT_PROJECT` to a project directory or its `project.godot` marker
(the target may not exist yet for `create_project`). No Python package or
engine SDK is required.

```bash
export A3GAME_GODOT_EXECUTABLE=/opt/godot/godot
export A3GAME_GODOT_PROJECT=/projects/MyGame

scripts/engine_install/godot/create_project.sh --name MyGame
python -m engine_adapters.godot --project "$A3GAME_GODOT_PROJECT" \
  install-framework
scripts/engine_install/godot/import_asset.sh --src model.glb
scripts/engine_install/godot/run.sh
```

Builds require a project-owned preset in `export_presets.cfg`:

```bash
python -m engine_adapters.godot --project "$A3GAME_GODOT_PROJECT" build \
  --preset "Linux/X11" --output builds/game.x86_64
```

Use a new output path for the first adapter-managed export. On subsequent
builds a signed ownership manifest permits replacement only while that export
and its companions still match their recorded content proofs. The signing key
lives in `A3GAME_GODOT_DATA_ROOT` (or `<project>/.a3game` by default); keep that
adapter state private and persistent. The build refuses edited manifests,
changed or unmanaged files, and project inputs such as `project.godot` and
`export_presets.cfg`. The data-root hierarchy must use ordinary directories,
not symbolic links or special filesystem nodes.

For browser delivery, configure a non-threaded Web export preset and optionally set
`A3GAME_GODOT_WEB_BUILD` and `A3GAME_GODOT_WEB_PRESET`. Export templates are a
Godot installation prerequisite; the adapter reports their absence as an export
failure rather than claiming a build. The repository does not include the
real-browser `SharedArrayBuffer` check needed to verify threaded/PWA embedding,
so that path is not a claimed capability.
