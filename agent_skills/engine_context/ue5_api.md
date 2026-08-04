# UE5 Agent API Reference

Status: implemented `UEClient` API version `v1`.

Validated engine baseline: Unreal Engine 5.4.

This file documents only APIs that exist in the current AAAGameForge source.
Do not treat examples, proposed features, private modules, or old OpenWL code
as public API.

## Hard API Boundary

An Agent working with Unreal MUST obey all of the following rules.

### Allowed Python Entry Point

```python
from engine_adapters.ue5 import UEClient
```

`UEClient` is the only supported Python entry point. Use only the namespace
objects and methods documented in this file.

### Allowed C++ Contract

Generated gameplay plugins may depend on the `AAAGamePlayable` module and may
include headers under:

```text
AAAGamePlayable/Source/AAAGamePlayable/Public/
```

With Unreal module include paths, generated source normally includes them as:

```cpp
#include "Components/AAAGameRuntimeEntityComponent.h"
#include "DataTypes/AAAGameRuntimeTypes.h"
#include "Interfaces/AAAGameControllableEntity.h"
#include "Interfaces/AAAGameEntityFactory.h"
#include "Interfaces/AAAGameRuntimeMessageHandler.h"
#include "Subsystems/AAAGameRuntimeSubsystem.h"
#include "Subsystems/AAAGameWorldSessionSubsystem.h"
```

### Forbidden

An Agent MUST NOT:

- import `engine_adapters.ue5._internal`;
- import namespace implementation classes such as `UEAssetsClient`;
- call transport, service, dispatcher, registry, or script-builder modules;
- execute arbitrary Unreal Python through a private transport;
- include `AAAGamePlayable` Private headers;
- modify the adapter-owned `AAAGamePlayable` framework;
- depend on or inherit from `ArenaFighterExample`, `FPSExample`, or
  `RacingExample`;
- pass arbitrary generated-output filesystem paths to asset or plugin methods;
- construct paths under `test_data/outputs` manually;
- assume a concrete Character, Pawn, Controller, GameMode, action set, or input
  mapping is supplied by the framework.

Concrete gameplay belongs in a separate project-local Gameplay Plugin.

## Execution Authority

`ue.testing.*` is public adapter API but is not callable by the
game-generation Agent during benchmark execution.

- The Agent generates engine-native Automation Test source.
- The Operator builds and executes generated tests.
- The Operator returns failures through the Repair Prompt.
- The Evaluator may independently execute benchmark-owned tests.
- The Agent MUST NOT invoke `ue.testing.*` or declare benchmark success.

Agent-generated tests support self-check and repair. Final benchmark scoring
may use Evaluator-owned hidden tests and MUST NOT rely only on tests authored
by the Agent.

## Client Construction

```python
UEClient(
    project_path: str | Path | None = None,
    ue_root: str | Path | None = None,
    api_version: str = "v1",
    *,
    host: str | None = None,
    port: int | None = None,
    runtime_host: str | None = None,
    runtime_port: int | None = None,
    python_transport: str | None = None,
    python_plugin_path: str | Path | None = None,
)
```

| Parameter | Required | Default | Meaning |
| --- | --- | --- | --- |
| `project_path` | Operation-dependent | environment or unset | Project directory or `.uproject` file |
| `ue_root` | Operation-dependent | environment or unset | Unreal Engine installation root |
| `api_version` | No | `"v1"` | Only `"v1"` is supported |
| `host` | No | `"127.0.0.1"` | Unreal Remote Control host |
| `port` | No | `30010` | Unreal Remote Control port |
| `runtime_host` | No | `"127.0.0.1"` | Runtime UDP input host |
| `runtime_port` | No | `30020` | Runtime UDP input port |
| `python_transport` | No | `"remote_execution"` | `"remote_execution"` or `"remote_control"` |
| `python_plugin_path` | No | derived from `ue_root` | Unreal Python plugin path |

Supported environment variables:

| Variable | Purpose |
| --- | --- |
| `AAAGAME_UE_ROOT` | Default `ue_root` |
| `AAAGAME_UE_PROJECT` | Default `project_path` |
| `AAAGAME_UE_HOST` or `UE_HOST` | Remote Control host |
| `AAAGAME_UE_PORT` or `UE_PORT` | Remote Control port |
| `AAAGAME_UE_RUNTIME_HOST` | Runtime UDP host |
| `AAAGAME_UE_RUNTIME_PORT` | Runtime UDP port |
| `AAAGAME_UE_PYTHON_TRANSPORT` | Python transport selection |
| `AAAGAME_UE_PYTHON_PLUGIN_PATH` or `UE_PYTHON_PLUGIN_PATH` | Python plugin path |
| `AAAGAME_UE_DATA_ROOT` or `AAAGAME_DATA_ROOT` | Adapter registry root |
| `AAAGAME_UE_ARTIFACT_REGISTRY` or `AAAGAME_ARTIFACT_REGISTRY` | Artifact registry file |
| `AAAGAME_UE_WORLD_REGISTRY_ROOT` or `AAAGAME_WORLD_REGISTRY_ROOT` | World registry root |

Example:

```python
from engine_adapters.ue5 import UEClient

ue = UEClient(
    project_path="D:/Projects/FPSDemo/FPSDemo.uproject",
    ue_root="D:/UE/UE_5.4",
    api_version="v1",
    runtime_host="127.0.0.1",
    runtime_port=30020,
)
```

Public top-level members:

```text
ue.api_version
ue.get_environment_info()
ue.project
ue.assets
ue.animation
ue.bindings
ue.world
ue.plugin
ue.build
ue.testing
ue.runtime
ue.reflection
ue.observe
```

## Result Contract

Every operation returns a JSON-serializable `dict` with exactly these top-level
keys:

```text
ok
operation
artifacts
diagnostics
warnings
errors
payload
```

Example:

```python
result = ue.project.validate()
if not result["ok"]:
    raise RuntimeError("; ".join(result["errors"]))
```

| Key | Type | Meaning |
| --- | --- | --- |
| `ok` | `bool` | Authoritative success value |
| `operation` | `str` | Stable operation name such as `build.project` |
| `artifacts` | `list[dict]` | Produced or queried artifacts |
| `diagnostics` | `list[dict]` | Structured compiler/environment diagnostics |
| `warnings` | `list[str]` | Non-fatal warnings |
| `errors` | `list[str]` | Failure reasons |
| `payload` | `dict` | Operation-specific data |

Diagnostic entries may contain:

```text
severity
message
code
file
line
column
source
```

Rules:

- Always check `ok`.
- Do not infer success from an empty `errors` list.
- Persist failed operation results and build diagnostics for repair prompts.
- Do not treat a warning as a failure unless the task acceptance criteria
  require it.

## Generated Artifact Source Descriptor

Asset and generated-plugin methods accept a repository artifact descriptor,
not a raw source path:

```python
source = {
    "game_id": "gameA_cyberpunk_shooter",
    "run_id": "fps_baseline_v1",
    "task_kind": "3d_object",
    "task_id": "fps_rifle",
    "artifact_key": "fbx_path",
}
```

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `game_id` | Yes | none | Game project identity |
| `run_id` | No | `"default"` | Generation run identity |
| `task_kind` | Sometimes | inferred from asset type when unambiguous | Registered task kind |
| `task_id` | Yes | none | Source task identity |
| `artifact_key` | Sometimes | inferred only when exactly one artifact path exists | Key in task `meta.json` |

Default asset-type mappings:

| Asset type | Default `task_kind` |
| --- | --- |
| `avatar`, `effect`, `environment`, `material`, `prop`, `static_mesh`, `texture`, `weapon` | `3d_object` |
| `scene` | `3d_scene` |
| `motion` | `motion` |
| `audio` | `audio` |

Resolution rules:

- The task directory is resolved through `pipeline.common.paths`.
- The task must contain a valid `meta.json`.
- Identity fields in `meta.json` must not conflict with the descriptor.
- The selected artifact must remain inside its task directory.
- `artifact_key` is mandatory when zero or multiple `*_path` fields exist.
- Plugin installation normally uses `task_kind="mechanic"` and
  `artifact_key="plugin_dir"`.

`ue.assets.resolve_source()` exposes the resolved path for diagnostics. Do not
take that returned path and feed it back into another UEClient source argument.

## Namespace Summary

| Namespace | Responsibility |
| --- | --- |
| `project` | Inspect, create, and validate minimal UE projects |
| `assets` | Resolve, validate, import, and query generated assets |
| `animation` | Motion import and Skeleton compatibility |
| `bindings` | Bind generated PBR material packages |
| `world` | Build scenes and manage World drafts/packages |
| `plugin` | Install generated plugins and the runtime framework |
| `build` | Compile Unreal Editor or Game targets |
| `testing` | Execute and parse engine-native Automation Tests |
| `runtime` | Launch/stop Editor and manage generic runtime sessions |
| `reflection` | Inspect registered UE artifacts |
| `observe` | Check Remote Control and Python readiness |

# Python API

## Environment Information

### `ue.get_environment_info`

```python
ue.get_environment_info() -> dict
```

Returns `operation="client.get_environment_info"` with payload fields:

```text
api_version
engine_version
ue_root
ue_root_exists
project_path
project_file
project_exists
remote_control_url
python_transport
runtime_input_host
runtime_input_port
```

This operation does not require a live Editor.

## Project

### `ue.project.get_info`

```python
ue.project.get_info() -> dict
```

Reports resolved engine/project paths and existence flags. It does not validate
the full environment and does not connect to Unreal.

### `ue.project.create`

```python
ue.project.create(
    *,
    dry_run: bool = False,
) -> dict
```

Creates the project configured by the `UEClient` constructor.

| Parameter | Meaning |
| --- | --- |
| `dry_run` | Validate and return the creation plan without writing files |

Created project contents:

- one minimal C++ host module;
- Game and Editor targets;
- `Content/Imported/*` directories;
- `Content/Maps`;
- `Plugins`;
- available engine automation plugin entries;
- `Config/DefaultEngine.ini`;
- `.aaagame-ue.json`.

It does not:

- install `AAAGamePlayable`;
- install a generated gameplay plugin;
- define a Character, Pawn, Controller, HUD, or GameMode;
- compile the project.

Important failure conditions:

- missing `ue_root` or `project_path`;
- Unreal Editor executable not found;
- invalid C++ project name;
- target `.uproject` already exists.

`payload` includes:

```text
ue_root
editor
project_dir
project_file
project_name
editor_target
game_target
plugins
dry_run
```

### `ue.project.validate`

```python
ue.project.validate() -> dict
```

Validates:

- configured `ue_root` exists;
- `project_path` resolves to exactly one `.uproject`;
- the project file exists.

It does not require a live Editor and does not compile.

## Assets

All import operations require a generated artifact source descriptor. Actual
import execution normally requires a connected Unreal Python environment.

When `destination=""`, the adapter chooses the type-specific default:

```text
/Game/Imported/Avatars
/Game/Imported/Motions
/Game/Imported/Scenes
/Game/Imported/Environments
/Game/Imported/Effects
/Game/Imported/Materials
/Game/Imported/Textures
/Game/Imported/Props
/Game/Imported/Weapons
```

### Generic Import

```python
ue.assets.import_asset(
    source: Mapping[str, Any],
    asset_type: str,
    *,
    destination: str = "",
    options: dict[str, Any] | None = None,
) -> dict
```

Supported configured asset types include:

```text
avatar
motion
scene
environment
effect
material
texture
prop
weapon
static_mesh
```

`options` is passed to the asset backend. Use only options defined by the
selected task/Skill. Common launcher options currently include:

```text
category
generate_collision
```

Effect imports are routed to the Effect service.

### Typed Import Methods

```python
ue.assets.import_avatar(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
)

ue.assets.import_scene(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
)

ue.assets.import_prop(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
)

ue.assets.import_weapon(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
)

ue.assets.import_material(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
)

ue.assets.import_texture(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
)
```

These methods call `import_asset` with the corresponding type and return an
operation name matching the typed method.

`import_scene` imports a scene asset. Use `ue.world.build` when the requirement
is to construct/publish a playable World or native map.

### Motion Import

```python
ue.assets.import_motion(
    source,
    *,
    skeleton: str,
    destination: str = "",
    avatar_name: str = "",
    options: dict | None = None,
) -> dict
```

| Parameter | Required | Meaning |
| --- | --- | --- |
| `skeleton` | Yes | UE Skeleton asset path |
| `destination` | No | Destination root |
| `avatar_name` | No | Optional avatar naming hint |
| `options` | No | Additional import options |

Motion import fails before connecting to Unreal when `skeleton` is empty.
Never guess Skeleton compatibility from filenames.

### Effect Import

```python
ue.assets.import_effect(
    source,
    *,
    destination: str = "",
    options: dict | None = None,
) -> dict
```

Recognized effect options:

| Option | Default | Meaning |
| --- | --- | --- |
| `effect_id` | `""` | Effect package identity |
| `entry_id` | `""` | Entry identity |
| `entry_asset` | `""` | Explicit entry asset |
| `replace_existing` | `False` | Replace existing destination |

Unknown effect options are ignored and reported in `warnings`.

### Asset Validation

```python
ue.assets.validate(
    source,
    asset_type: str,
    *,
    destination: str = "",
    options: dict | None = None,
) -> dict
```

Validates the generated source and import contract without requiring an active
Editor connection for the current validation paths.

### Source Resolution

```python
ue.assets.resolve_source(
    source,
    *,
    asset_type: str = "",
) -> dict
```

Returns:

```text
payload.source
payload.path
payload.meta_path
payload.metadata
```

Scene sources may resolve to a file or directory.

### Live Asset Query

```python
ue.assets.list(
    asset_type: str = "",
    *,
    root: str = "/Game/Imported",
) -> dict
```

Queries Unreal assets under `root`. This normally requires a ready Unreal
Python environment.

### Registered Artifact Query

```python
ue.assets.list_registered(
    asset_type: str = "",
) -> dict
```

Reads the adapter artifact registry and returns matching UE artifact records.
This does not require a live Editor.

Payload:

```text
asset_type
count
registry_path
```

### Registered Artifact Metadata

```python
ue.assets.get_metadata(
    artifact_id: str,
) -> dict
```

Fails with `Unknown artifact_id` when the record is absent.

## Animation

### `ue.animation.import_motion`

```python
ue.animation.import_motion(
    source,
    *,
    skeleton: str,
    destination: str = "",
    avatar_name: str = "",
    options: dict | None = None,
) -> dict
```

This is the animation namespace alias for `ue.assets.import_motion`.

### `ue.animation.resolve_skeleton`

```python
ue.animation.resolve_skeleton(
    avatar: str,
) -> dict
```

`avatar` may match a registered avatar's:

```text
artifact_id
asset_id
backend_path
```

Resolution checks the artifact registry first, then the live UE asset registry.

Success payload:

```text
avatar
skeleton
source
```

### `ue.animation.validate_compatibility`

```python
ue.animation.validate_compatibility(
    motion: str,
    skeleton: str,
) -> dict
```

Compares a registered Motion's Skeleton dependency with `skeleton`.

Success or mismatch payload:

```text
motion
expected_skeleton
actual_skeleton
```

The operation fails for an empty Skeleton or unknown registered Motion.

## Bindings

### `ue.bindings.bind_pbr_material`

```python
ue.bindings.bind_pbr_material(
    *,
    asset_id: str,
    source: Mapping[str, Any],
    mesh_assets: list[str],
    destination: str,
    options: dict[str, Any] | None = None,
) -> dict
```

| Parameter | Required | Meaning |
| --- | --- | --- |
| `asset_id` | Yes | Logical material binding identity |
| `source` | Yes | Generated material source descriptor |
| `mesh_assets` | Yes | UE mesh asset paths receiving the material |
| `destination` | Yes | UE material destination root |
| `options` | No | Material configuration |

This operation requires Unreal Python execution.

## World

### `ue.world.build`

```python
ue.world.build(
    source: Mapping[str, Any],
    *,
    options: dict[str, Any] | None = None,
) -> dict
```

### Native Environment Import And Readiness

For native UE content packs, the execution harness should prefer public
`UEClient` asset/world calls. If direct orchestration cannot reliably manage
Editor readiness or lifecycle, use:

```text
scripts/ue/import_asset.sh
scripts/ue/import_asset.cmd
```

These launchers call `engine_adapters.ue5.cli`, which calls only public
`UEClient` operations. They still require task descriptors and are not a raw
path bypass.

When `python_transport="remote_execution"`, successful Unreal Python execution
is sufficient for asset and world import even if optional Remote Control HTTP
is unavailable. Preserve the launcher JSON result and Editor logs.

After import, warm the native map before runtime acceptance. Wait for derived
data, shader, texture, and streaming work to stabilize; inspect the real game
window; reject blank, near-white, near-black, or severely exposed frames; and
resolve lighting-build and texture-pool warnings rather than merely hiding
their messages.

Builds a generated scene source into Unreal World/map artifacts.

Recognized options:

| Option | Default | Meaning |
| --- | --- | --- |
| `world_id` | `""` | Logical World identity |
| `project_id` | `""` | Logical project identity |
| `publish` | `True` | Publish a runtime World package |
| `default_spawn_point` | unset | Default spawn transform/point |
| `native_map` | `""` | Explicit native map path |
| `replace_existing` | `False` | Replace existing outputs |
| `preview_in_editor` | `True` | Preview the result in Editor |
| `repair_missing_collision` | `False` | Attempt collision repair |

Unknown options are ignored and listed in `warnings`.

### `ue.world.create_draft`

```python
ue.world.create_draft(
    spec: Mapping[str, Any],
    *,
    draft_id: str = "",
    project_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict
```

Creates a registry-backed World draft. It does not import source files.

Implemented WorldSpec version:

```json
{
  "version": "1.0",
  "world_id": "arena",
  "project_id": "demo",
  "entities": [
    {
      "entity_id": "arena_root",
      "role": "environment",
      "artifact_id": "ue_static_mesh_arena",
      "category": "",
      "collision": true,
      "transform": {
        "location": {"x": 0.0, "y": 0.0, "z": 0.0},
        "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0}
      },
      "behaviors": [
        {
          "type": "motion",
          "artifact_id": "ue_motion_idle",
          "loop": true,
          "options": {}
        }
      ]
    }
  ],
  "camera": {
    "mode": "orbit",
    "target": "arena_root"
  },
  "metadata": {}
}
```

WorldSpec rules:

- supported `version` is `"1.0"`;
- entity roles are `environment`, `prop`, and `avatar`;
- each entity requires a registered `artifact_id`;
- supported behavior type is `motion`;
- collision defaults to enabled for `environment` and `prop`;
- transform vectors may be objects or three-element lists;
- arbitrary `/Game/...` paths are not valid replacements for artifact IDs.

Success payload:

```text
payload.draft
```

### `ue.world.validate_draft`

```python
ue.world.validate_draft(
    draft_id: str,
) -> dict
```

Validates draft structure and referenced registered artifacts.

### `ue.world.publish_draft`

```python
ue.world.publish_draft(
    draft_id: str,
) -> dict
```

Publishes a validated draft as a World package.

Success payload:

```text
payload.package
```

### `ue.world.list_packages`

```python
ue.world.list_packages(
    *,
    project_id: str = "",
    world_id: str = "",
) -> dict
```

Returns matching `world_package` artifacts and `payload.count`.

## Plugin

### `ue.plugin.install`

```python
ue.plugin.install(
    source: Mapping[str, Any],
    *,
    replace_existing: bool = False,
    dry_run: bool = False,
) -> dict
```

Installs a generated plugin artifact into:

```text
<Project>/Plugins/<PluginName>/
```

Source requirements:

- descriptor resolves to a plugin directory or `.uplugin` file;
- a plugin directory contains exactly one top-level `.uplugin`;
- plugin name comes from the descriptor filename.

If the generated `.uplugin` declares:

```json
{
  "Plugins": [
    {"Name": "AAAGamePlayable", "Enabled": true}
  ]
}
```

then `install()` synchronizes and enables `AAAGamePlayable` first.

| Parameter | Meaning |
| --- | --- |
| `replace_existing` | Permit synchronization into an existing plugin target |
| `dry_run` | Return the installation plan without copying or modifying `.uproject` |

Payload includes:

```text
source
plugin_name
descriptor
target
replace_existing
dry_run
requires_framework
copied_files
framework
```

### `ue.plugin.install_framework`

```python
ue.plugin.install_framework(
    *,
    dry_run: bool = False,
) -> dict
```

Synchronizes and enables the adapter-owned `AAAGamePlayable` plugin.

Generated game workflows normally use `ue.plugin.install`, which calls this
automatically when the dependency is declared.

### `ue.plugin.list`

```python
ue.plugin.list() -> dict
```

Lists project plugins found at:

```text
<Project>/Plugins/*/*.uplugin
```

Returns plugin artifacts and `payload.count`.

## Build

### `ue.build.project`

```python
ue.build.project(
    *,
    target: str = "",
    configuration: str = "Development",
    clean: bool = False,
    dry_run: bool = False,
    timeout: float | None = None,
) -> dict
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `target` | project Editor target | Unreal target name |
| `configuration` | `"Development"` | Unreal build configuration |
| `clean` | `False` | Add `-Clean` |
| `dry_run` | `False` | Return command without executing |
| `timeout` | `None` | Subprocess timeout in seconds |

Default target:

```text
<ProjectName>Editor
```

To compile the Game target:

```python
ue.build.project(target="<ProjectName>")
```

Payload includes:

```text
command
cwd
target
platform
configuration
clean
dry_run
returncode
stdout
stderr
```

Compiler warnings/errors recognized from UnrealBuildTool output are returned in
`diagnostics`.

## Testing

Executor:

```text
Operator / Evaluator only
```

The game-generation Agent may read this contract so it can generate compatible
Automation Test source, but it MUST NOT call this method.

### `ue.testing.run_automation_tests`

```python
ue.testing.run_automation_tests(
    test_filter: str,
    *,
    report_dir: str = "",
    extra_args: Sequence[str] = (),
    timeout: float | None = None,
    dry_run: bool = False,
) -> dict
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `test_filter` | required | Unreal Automation Test name or filter |
| `report_dir` | `""` | Report directory; empty uses `<Project>/Saved/Automation/Reports` |
| `extra_args` | `()` | Additional `UnrealEditor-Cmd` arguments |
| `timeout` | `None` | Process timeout in seconds |
| `dry_run` | `False` | Return the command without executing Unreal |

A relative `report_dir` is resolved from the Unreal project directory.
`extra_args` cannot override `ExecCmds`, `ReportExportPath`, or `TestExit`.
Use `extra_args=("-NullRHI",)` when the selected tests do not require
rendering.

The operation launches `UnrealEditor-Cmd` with:

```text
Automation RunTests <test_filter>; Quit
TestExit=Automation Test Queue Empty
ReportExportPath=<report_dir>
```

Success requires all of the following:

- the Unreal process exits with code `0`;
- a fresh `index.json` Automation Report is produced;
- at least one matching test is present;
- every matching test passed;
- no test failed, was skipped, did not run, remained in process, or had an
  unknown state;
- report summary counts agree with individual test states.

A zero process return code alone is not success.

The report directory is returned as:

```json
{
  "type": "automation_report",
  "path": "...",
  "state": "ready"
}
```

The report artifact is retained when tests fail or the process exits nonzero,
provided the current run produced a fresh report.

Payload fields:

```text
command
cwd
test_filter
report_dir
report_file
dry_run
returncode
stdout
stderr
timed_out
report_created_on
total_duration
tests_found
tests_passed
tests_succeeded
tests_succeeded_with_warnings
tests_failed
tests_not_run
tests_in_process
tests_skipped
tests_unknown
```

Automation Report errors and warnings are returned through `diagnostics`.
Successful tests with warnings keep `ok=True` and add a top-level warning.
Missing configuration, an empty filter, invalid controlled arguments, timeout,
missing/stale/invalid reports, no matched tests, and any non-passing state
return `ok=False`.

Formal Mechanic runs should pass:

```text
test_data/outputs/<game_id>/<run_id>/mechanic/<task_id>/
demo_outputs/automation/
```

## Runtime Process

### `ue.runtime.launch_editor`

```python
ue.runtime.launch_editor(
    *,
    map_path: str = "",
    extra_args: Sequence[str] = (),
    dry_run: bool = False,
) -> dict
```

Launches Unreal Editor for the configured project. There is no public
`launch_game` method in UEClient v1.

The launch command includes:

```text
WebControl.StartServer <remote control port>
-NoSplash
-Log
-AAAGameRuntimeInputPort=<runtime port>
```

| Parameter | Meaning |
| --- | --- |
| `map_path` | Optional map argument such as `/Game/Maps/Arena` |
| `extra_args` | Additional Unreal command-line arguments |
| `dry_run` | Return command without launching |

Successful live launch returns `payload.process_id`.

### `ue.runtime.stop_editor`

```python
ue.runtime.stop_editor(
    process_id: int,
) -> dict
```

UEClient can stop only Editor processes launched by the same `UEClient`
instance. Unknown process IDs fail.

## Runtime Sessions

Runtime sessions manage generic participants, controllers, entity bindings,
normalized movement input, and a UDP bridge to `AAAGamePlayable`.

They do not define combat actions, weapons, vehicle controls, or game rules.

### `ue.runtime.sessions.join`

```python
ue.runtime.sessions.join(
    *,
    world_id: str = "",
    participant_id: str = "",
    user_id: str = "",
    avatar_artifact_id: str = "",
    idle_motion_artifact_id: str = "",
    move_motion_artifact_id: str = "",
    controller_kind: str = "human",
    transform: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict
```

| Parameter | Meaning |
| --- | --- |
| `world_id` | Runtime World identity; defaults internally to `world_001` |
| `participant_id` | Stable participant identity; generated when empty |
| `user_id` | Optional external user identity |
| `avatar_artifact_id` | Registered UE avatar artifact |
| `idle_motion_artifact_id` | Registered UE Motion artifact |
| `move_motion_artifact_id` | Registered UE Motion artifact |
| `controller_kind` | Controller label such as `human` or `agent` |
| `transform` | Spawn transform object |
| `parameters` | Gameplay-plugin-defined string/object parameters |

Transform shape:

```json
{
  "location": {"x": 0.0, "y": 0.0, "z": 100.0},
  "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
  "scale": {"x": 1.0, "y": 1.0, "z": 1.0}
}
```

Artifact IDs must exist in the UE artifact registry and have the expected
types.

Success payload includes:

```text
world_id
participant_id
controller_id
entity_id
view_mode
entity_persistent
ue_input
ue_bridge
avatar_artifact_id
idle_motion_artifact_id
move_motion_artifact_id
```

The UE bridge is asynchronous. `join()` may report that synchronization was
queued before the UE actor has completed spawning.

### `ue.runtime.sessions.leave`

```python
ue.runtime.sessions.leave(
    *,
    participant_id: str = "",
    controller_id: str = "",
) -> dict
```

Marks the participant/controller offline and disables the binding. The
persistent entity is retained.

### `ue.runtime.sessions.heartbeat`

```python
ue.runtime.sessions.heartbeat(
    controller_id: str,
) -> dict
```

Marks the controller and participant online and refreshes their timestamps.
Unknown controller IDs fail.

### `ue.runtime.sessions.apply_input`

```python
ue.runtime.sessions.apply_input(
    controller_id: str,
    *,
    move_x: float = 0.0,
    move_y: float = 0.0,
    run: bool = False,
    jump: bool = False,
    yaw: float = 0.0,
    pitch: float = 0.0,
    seq: int = 0,
) -> dict
```

Input rules:

- `move_x` and `move_y` are clamped to `[-1.0, 1.0]`;
- `run` and `jump` are generic normalized states;
- `yaw` and `pitch` are control/view values;
- `seq` is caller-provided ordering metadata;
- the controller must have an active entity binding.

Success payload includes:

```text
world_id
participant_id
controller_id
entity_id
queued
locomotion_state
seq
ue_bridge
```

`locomotion_state` is one of:

```text
idle
walk
run
jump
```

The generated controllable entity decides how normalized input becomes actual
movement.

### `ue.runtime.sessions.snapshot`

```python
ue.runtime.sessions.snapshot(
    *,
    world_id: str = "",
) -> dict
```

Returns a broker snapshot containing:

```text
participants
controllers
bindings
entities
avatars
bridge_errors
bridge_status
bridge_queue_size
server_time
```

UE remains authoritative for actual actor physics. Bridge-updated actor
locations may arrive asynchronously.

### `ue.runtime.sessions.reset_world`

```python
ue.runtime.sessions.reset_world(
    *,
    world_id: str = "",
) -> dict
```

Clears adapter-side participant, controller, entity, binding, and input state
for the selected World.

This operation does not itself guarantee that every UE actor was destroyed.
Use it after the UE-side World/runtime actors have been reset.

### `ue.runtime.sessions.clear_entity`

```python
ue.runtime.sessions.clear_entity(
    *,
    participant_id: str = "",
    controller_id: str = "",
    entity_id: str = "",
    destroy_actor: bool = True,
) -> dict
```

Clears one participant/entity and associated controllers/bindings.

When `destroy_actor=True` and the bridge is enabled, UE actor destruction is
queued asynchronously.

## Reflection

### `ue.reflection.inspect_artifact`

```python
ue.reflection.inspect_artifact(
    artifact_id: str,
    *,
    live: bool = True,
) -> dict
```

| `live` | Behavior |
| --- | --- |
| `False` | Return the registered artifact record only |
| `True` | Load and inspect the asset in Unreal through Python execution |

Live success payload contains:

```text
artifact
live
inspection.asset_path
inspection.name
inspection.class
inspection.class_path
inspection.package
```

## Observation

### `ue.observe.check_status`

```python
ue.observe.check_status(
    *,
    timeout: float = 5.0,
    check_python: bool = True,
) -> dict
```

Checks:

- Remote Control reachability;
- Unreal Python execution when `check_python=True`.

Payload:

```text
api_version
remote_control.ok
remote_control.url
python_execution.checked
python_execution.ok
python_execution.transport
```

The operation returns `ok=False` and structured diagnostics when the
environment is not ready.

# AAAGamePlayable C++ Public Contract

## Plugin Dependency

Generated `.uplugin`:

```json
{
  "FileVersion": 3,
  "EnabledByDefault": false,
  "Modules": [
    {
      "Name": "GeneratedGameplayPlugin",
      "Type": "Runtime",
      "LoadingPhase": "Default"
    }
  ],
  "Plugins": [
    {
      "Name": "AAAGamePlayable",
      "Enabled": true
    }
  ]
}
```

Generated `Build.cs`:

```csharp
PublicDependencyModuleNames.AddRange(new[]
{
    "Core",
    "CoreUObject",
    "Engine",
    "AAAGamePlayable"
});
```

Do not add framework Private include paths.

## Runtime Enums

### `EAAAGameControlMode`

```text
Exclusive
Priority
Assisted
Observing
```

### `EAAAGameLocomotionState`

```text
Idle
Walk
Run
Jump
```

## Runtime Data Types

### `FAAAGameRuntimeInputState`

```text
WorldId
ParticipantId
ControllerId
EntityId
MoveX
MoveY
bRun
bJump
Yaw
Pitch
Sequence
TimestampSeconds
```

### `FAAAGameEntitySpawnRequest`

```text
WorldId
ParticipantId
EntityId
Transform
Parameters: TMap<FString, FString>
```

### `FAAAGameParticipantInfo`

```text
ParticipantId
WorldId
UserId
EntityId
bOnline
```

### `FAAAGameControllerState`

```text
ControllerId
ParticipantId
WorldId
Kind
bOnline
```

### `FAAAGameControlBinding`

```text
ControllerId
EntityId
WorldId
Mode
Priority
bActive
```

### `FAAAGameEntitySnapshot`

```text
EntityId
ActorLabel
Position
Rotation
LocomotionState
MotionState
bPersistent
LastInputTimeSeconds
```

## `IAAAGameControllableEntity`

A generated controllable Character/Pawn may implement:

```cpp
FString GetRuntimeEntityId() const;
void SetRuntimeEntityId(const FString& EntityId);
bool ApplyRuntimeInput(
    const FAAAGameRuntimeInputState& InputState);
FAAAGameEntitySnapshot GetRuntimeSnapshot() const;
```

For a `BlueprintNativeEvent`, C++ implementations override:

```cpp
GetRuntimeEntityId_Implementation
SetRuntimeEntityId_Implementation
ApplyRuntimeInput_Implementation
GetRuntimeSnapshot_Implementation
```

The generated plugin owns physical movement, camera behavior, actions, combat,
AI, and gameplay state.

## `IAAAGameEntityFactory`

```cpp
AActor* SpawnRuntimeEntity(
    const FAAAGameEntitySpawnRequest& Request);
```

C++ implementations override:

```cpp
SpawnRuntimeEntity_Implementation
```

The factory must spawn the generated game's own concrete actor. It must not
spawn a framework-owned gameplay actor because none exists.

## `IAAAGameRuntimeMessageHandler`

```cpp
bool HandleRuntimeMessage(
    const FString& MessageType,
    const FString& JsonPayload);
```

This is the public extension-message handler contract. UEClient v1 does not
currently expose a generic Python method for sending arbitrary extension
messages, so do not assume one exists.

## `UAAAGameIdentityComponent`

Public method:

```cpp
void SetRuntimeIdentity(
    const FString& InParticipantId,
    const FString& InEntityId);
```

Replicated public fields:

```text
ParticipantId
EntityId
```

## `UAAAGameRuntimeEntityComponent`

Public methods:

```cpp
void SetRuntimeEntityId(const FString& InEntityId);
bool ApplyRuntimeInput(
    const FAAAGameRuntimeInputState& InputState);
FAAAGameEntitySnapshot GetRuntimeSnapshot() const;
```

Public fields/events:

```text
EntityId
bPersistent
LocomotionState
MotionState
OnRuntimeInput
```

The component updates generic runtime state and broadcasts normalized input.
It does not move the owner automatically.

## `UAAAGameRuntimeSubsystem`

Public methods:

```cpp
void SetEntityFactory(UObject* FactoryObject);
void RegisterMessageHandler(UObject* HandlerObject);
void UnregisterMessageHandler(UObject* HandlerObject);
UAAAGameWorldSessionSubsystem* GetSessionSubsystem() const;
```

`SetEntityFactory` expects an object implementing `IAAAGameEntityFactory`.

Generated plugins normally create a World subsystem that registers their
factory during `OnWorldBeginPlay`.

## `UAAAGameWorldSessionSubsystem`

Public methods:

```cpp
void SetEntityFactory(UObject* FactoryObject);

FAAAGameParticipantInfo RegisterParticipant(
    const FString& ParticipantId,
    const FString& UserId);

void MarkParticipantOffline(
    const FString& ParticipantId);

AActor* SpawnEntity(
    const FAAAGameEntitySpawnRequest& Request);

bool RegisterEntity(
    const FString& EntityId,
    AActor* Actor,
    const FString& ParticipantId);

bool RemoveEntity(
    const FString& EntityId,
    bool bDestroyActor);

FAAAGameControllerState CreateController(
    const FString& ParticipantId,
    const FString& ControllerId,
    const FString& Kind);

bool BindControllerToEntity(
    const FString& ControllerId,
    const FString& EntityId,
    EAAAGameControlMode Mode,
    int32 Priority);

bool UnbindController(
    const FString& ControllerId);

bool EnqueueInputState(
    const FAAAGameRuntimeInputState& InputState);

TArray<FAAAGameEntitySnapshot>
GetWorldStateSnapshot() const;

AActor* GetActorForEntity(
    const FString& EntityId) const;
```

Configurable fields:

```text
WorldId = "world_001"
InputConsumeHz = 20.0
```

## Minimal Generated Runtime Registration

The canonical pattern is:

1. Implement a game-owned Pawn/Character and
   `IAAAGameControllableEntity`.
2. Implement a game-owned `IAAAGameEntityFactory`.
3. Create a game-owned `UWorldSubsystem`.
4. In `OnWorldBeginPlay`, create the factory and call
   `UAAAGameRuntimeSubsystem::SetEntityFactory`.
5. Clear the factory during subsystem deinitialization.

Reference implementation:

```text
test/fixtures/GeneratedGameplayPlugin/
```

Optional concrete references:

```text
engine_adapters/ue5/examples/ArenaFighterExample/
engine_adapters/ue5/examples/FPSExample/
engine_adapters/ue5/examples/RacingExample/
```

Use these examples as implementation patterns only. Do not add them as
dependencies and do not inherit their concrete classes.

# Recommended Agent Workflow

For one Mechanic task:

1. Read the task requirement and generated artifact descriptors.
2. Construct `UEClient` with the target project and Unreal root.
3. Call `ue.get_environment_info()` and `ue.project.validate()`.
4. Call `ue.project.create()` only when the target project does not exist.
5. Validate/import assets through descriptors.
6. Generate a separate Gameplay Plugin in the Mechanic task output directory.
7. Declare `AAAGamePlayable` as a plugin/module dependency.
8. Install through `ue.plugin.install()`.
9. Generate engine-native Automation Test source inside the Gameplay Plugin.
10. Compile Editor and required Game targets through `ue.build.project()`.
11. The Operator executes generated tests through
    `ue.testing.run_automation_tests()` and returns failures for repair.
12. Launch Editor through `ue.runtime.launch_editor()`.
13. Poll `ue.observe.check_status()` with a bounded timeout.
14. Join a runtime session, apply normalized inputs, and inspect snapshots.
15. Save the complete project source, plugin source, build results, trace,
    screenshots, selected Skills, Agent transcript, and `meta.json`.

Build or runtime failure handling:

- preserve the full failed operation result;
- use `diagnostics`, `stdout`, and `stderr` in the repair prompt;
- do not bypass a failure by importing private APIs;
- retry only with a bounded repair count;
- rerun validation after every repair;
- never delete the generated project after evaluation.

# Boundary By Agent Type

## Mechanic Agent

- May receive one selected engine API reference and one relevant optional
  example.
- Generates a complete project-local Gameplay Plugin.
- Uses only artifact descriptors for generated inputs.
- Uses only `AAAGamePlayable` Public headers.
- Owns concrete input mapping, movement, rules, AI, weapons, and gameplay
  state.
- Generates engine-native Automation Test source.
- Must not call `ue.testing.*` or declare benchmark success.

## Mechanic Operator And Evaluator

- The Operator performs authoritative builds and executes Agent-generated
  tests through `ue.testing`.
- The Operator returns failures through a bounded Repair Prompt.
- The Evaluator may install or inject benchmark-owned tests and execute them
  through the same public testing API.
- Final benchmark scoring must not rely only on Agent-generated tests.

## UI Agent

- For `ui_target="ue_runtime"`, generates UE HUD/menu code against public
  generated-game state contracts.
- May use UEClient only at the UI Operator's engine boundary for installation,
  build, reflection, and observation.
- Must not import transports or adapter internals.
- Browser/platform APIs are not documented here.

## Full Pipeline

- Must not import or construct `UEClient`.
- Orchestrates existing asset, Mechanic, and UI artifacts through their
  Operators and task descriptors.
- Must not inspect adapter `_internal` modules.
