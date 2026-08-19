# UE5 Agent API Reference

Status: implemented `UEClient` API version `v1`.

Validated engine baseline: Unreal Engine 5.4.

This file is a compact index of implemented public capabilities. It lists
public names and their functions only. Read the current source when exact
parameters or result payload fields are required.

## Host-Side API Boundary

For host-side Python code, the only supported Unreal entry point is:

```text
from engine_adapters.ue5 import UEClient
```

Agents, Pipeline code, execution/evaluation composition roots, repository
scripts, and platform Serving backends must not:

- import `engine_adapters.ue5._internal`;
- import namespace client implementation classes directly;
- call transports, services, dispatchers, registries, or script builders;
- execute arbitrary Unreal Python through private transports;
- modify the adapter-owned `A3GamePlayable` framework;
- include `A3GamePlayable` Private headers;
- depend on optional Arena Fighter, FPS, or Racing example plugins;
- construct generated-output paths manually.

Host-side code must not replace a public `UEClient` operation with a direct
`UnrealEditor`, `Build.bat`, `unreal.AssetImportTask`, or ad-hoc Unreal Python
launcher. The repository `scripts/ue/import_asset` wrappers are lifecycle
wrappers around the same public Client contract, not a second import API.

### Native Plugin Boundary

Generated Unreal Gameplay and UI Plugins run inside Unreal and may use the
documented native Unreal C++ APIs available to the project. They do not
import or call Python `UEClient`.

```text
Host-side project/import/build/runtime lifecycle -> UEClient
Native Unreal Gameplay/UI Plugin                 -> Unreal native C++ API
```

Native plugins remain project-local, use only permitted public
`A3GamePlayable` headers and normal Unreal module dependencies, and do not
reach into `engine_adapters/ue5` private implementation code.

### Execution Composition Root

The generation Agent may produce native plugin source and tests, but does not
run the Engine or claim authoritative build/playability success. The later
Execution/Assembly composition root may reuse one configured `UEClient`
session to validate and prepare the project, import descriptors, install
plugins, build targets, run authoritative tests, and launch or stop the
runtime.

If a required operation is missing from `UEClient`, report a public API
capability gap and extend the public Client/adapter contract first. Do not
create a game-owned parallel importer or build system.

## Execution Authority

The game-generation Agent generates engine-native test source. The Agent MUST
NOT invoke `ue.testing.*` or declare benchmark success.

Engine execution and evaluation code owns builds, Automation Test execution,
runtime evidence, and benchmark results. The generation Agent must not invoke
`ue.testing.*`; the later Execution/Assembly authority may invoke it through
`UEClient`. A zero process return code alone is not success; Automation Reports
must contain matching passing tests.

## Result Contract

Public operations return JSON-serializable result dictionaries using these
stable top-level fields:

- `ok` - whether the operation completed successfully;
- `operation` - stable operation identifier;
- `artifacts` - produced or retained artifact paths;
- `diagnostics` - structured diagnostic records;
- `warnings` - non-fatal problems;
- `errors` - fatal problems;
- `payload` - operation-specific result data.

## Client

- `UEClient` - Creates the public Unreal environment client and its namespace
  clients.
- `ue.api_version` - Reports the active public UEClient API version.
- `ue.get_environment_info` - Reports configured project, Engine, transport,
  and runtime environment information.

## Project

- `ue.project.get_info` - Reports the configured Unreal project and Engine
  paths.
- `ue.project.create` - Creates a minimal C++ Unreal host project without
  concrete gameplay defaults.
- `ue.project.validate` - Checks project configuration, descriptor, Engine,
  source, and required project structure.

## Assets

- `ue.assets.import_asset` - Imports a registered task artifact using its
  declared asset type.
- `ue.assets.import_avatar` - Imports a registered character or avatar
  artifact.
- `ue.assets.import_motion` - Imports registered animation data against an
  explicit target Skeleton.
- `ue.assets.import_scene` - Imports a registered Scene artifact.
- `ue.assets.import_prop` - Imports a registered prop or generic mesh artifact.
- `ue.assets.import_weapon` - Imports a registered weapon mesh artifact.
- `ue.assets.import_material` - Imports a registered material artifact.
- `ue.assets.import_texture` - Imports a registered texture artifact.
- `ue.assets.import_effect` - Imports a validated Effect package or native
  Effect content.
- `ue.assets.validate` - Validates a registered source artifact without
  requiring a live Unreal connection when possible.
- `ue.assets.resolve_source` - Resolves a repository task identity to its
  registered source artifact.
- `ue.assets.list` - Lists assets visible from a live Unreal project.
- `ue.assets.list_registered` - Lists artifacts recorded in the adapter
  registry.
- `ue.assets.get_metadata` - Reads metadata for one registered artifact.

Public asset methods consume repository task identities or the documented
public descriptor shape. They do not accept arbitrary generated-output
filesystem paths assembled by callers. Resolve sources through the Client and
preserve the structured result and artifact identity it returns.

### Import Lifecycle

`scripts/ue/import_asset` is a lifecycle wrapper around the same public
`UEClient`; it is not a second or faster asset API. Host-side batch execution
should reuse one configured Client and one running Editor session instead of
launching a separate Unreal process for every asset.

Direct asset and World operations expect Unreal Python execution to be ready.
Execution code should reuse one `UEClient` and one running Editor session for a
task batch instead of recreating or relaunching them for every asset.

The repository import launcher checks readiness, launches the Editor only when
needed, and can continue when Python execution is ready even if optional Remote
Control readiness is unavailable.

## Animation

- `ue.animation.import_motion` - Imports motion through the Animation
  namespace.
- `ue.animation.resolve_skeleton` - Resolves the Skeleton associated with a
  registered avatar or imported asset.
- `ue.animation.validate_compatibility` - Checks whether motion and Skeleton
  artifacts are compatible.

## Bindings

- `ue.bindings.bind_pbr_material` - Creates or updates a PBR material binding
  for an imported asset.

## World

- `ue.world.build` - Builds or imports a World from a registered Scene
  artifact.
- `ue.world.create_draft` - Creates a persistent editable World draft.
- `ue.world.validate_draft` - Validates a World draft and its referenced
  artifacts.
- `ue.world.publish_draft` - Publishes a validated draft as a registered World
  package.
- `ue.world.list_packages` - Lists registered World packages.

World operations preserve native Unreal content when a task supplies a native
project or map package.

## Plugin

- `ue.plugin.install` - Installs a registered generated Gameplay Plugin into a
  project and synchronizes declared framework dependencies.
- `ue.plugin.install_framework` - Installs the adapter-owned
  `A3GamePlayable` Runtime Framework.
- `ue.plugin.list` - Lists installed project plugins.

Generated Gameplay Plugins may depend only on `A3GamePlayable` Public headers.

## Build

- `ue.build.project` - Builds an Unreal project target and returns structured
  command and diagnostic evidence.

## Testing

- `ue.testing.run_automation_tests` - Runs Unreal Automation Tests, parses a
  fresh report, and returns authoritative matched, passed, and failed counts.

The game-generation Agent must not invoke this namespace. Only the later
Execution/Assembly authority may invoke it through `UEClient`.

## Runtime

- `ue.runtime.launch_editor` - Launches the configured Unreal Editor or game
  runtime process.
- `ue.runtime.stop_editor` - Stops Editor processes started by the same
  runtime client.

## Runtime Sessions

- `ue.runtime.sessions.join` - Creates or updates a generic participant,
  controller, entity, and control-binding session.
- `ue.runtime.sessions.leave` - Removes a participant from the runtime session.
- `ue.runtime.sessions.heartbeat` - Refreshes participant liveness.
- `ue.runtime.sessions.apply_input` - Applies normalized control input to a
  bound runtime entity.
- `ue.runtime.sessions.snapshot` - Returns the current generic runtime session
  state.
- `ue.runtime.sessions.reset_world` - Requests a generic runtime World reset.
- `ue.runtime.sessions.clear_entity` - Removes an entity and its associated
  bindings from session state.

Runtime sessions are game-neutral and do not define Fighter, FPS, or Racing
commands.

## Reflection

- `ue.reflection.inspect_artifact` - Inspects a registered imported artifact
  through Unreal reflection and returns structured metadata.

## Observation

- `ue.observe.check_status` - Reports Remote Control, Python execution,
  project, runtime, and observation readiness.

## A3GamePlayable Public C++ Contract

Generated Gameplay Plugins may include only headers under:

```text
A3GamePlayable/Source/A3GamePlayable/Public/
```

### Enums

- `EA3GameControlMode` - Identifies the generic control mode assigned to an
  entity.
- `EA3GameLocomotionState` - Represents generic locomotion state for runtime
  snapshots.

### Data Types

- `FA3GameRuntimeInputState` - Carries normalized movement, look, action, and
  input timing state.
- `FA3GameEntitySpawnRequest` - Describes a generic entity spawn request.
- `FA3GameParticipantInfo` - Describes one runtime participant.
- `FA3GameControllerState` - Describes one generic controller.
- `FA3GameControlBinding` - Connects a participant, controller, and entity.
- `FA3GameEntitySnapshot` - Reports observable generic entity state.

### Interfaces

- `IA3GameControllableEntity` - Contract implemented by game-owned
  controllable entities.
- `IA3GameEntityFactory` - Contract implemented by game-owned entity
  factories.
- `IA3GameRuntimeMessageHandler` - Contract for game-owned runtime message
  handling.

### Components

- `UA3GameIdentityComponent` - Stores stable runtime identity on a game-owned
  Actor.
- `UA3GameRuntimeEntityComponent` - Connects a game-owned Actor to runtime
  entity state and control.

### Subsystems

- `UA3GameRuntimeSubsystem` - Registers game-owned factories and coordinates
  generic runtime entity creation.
- `UA3GameWorldSessionSubsystem` - Owns generic participant, controller,
  entity, binding, input, and snapshot session state.

## Framework Boundaries

`A3GamePlayable` provides runtime contracts only. It does not provide a
concrete Character, Pawn, Controller, GameMode, HUD, weapon, vehicle, combat
rule, or game-specific input mapping.

Generated projects own concrete gameplay implementation. Optional Preview,
Arena Fighter, FPS, and Racing plugins are read-only references and are not
dependencies or success criteria.

This native C++ contract is intentionally separate from the host-side
`UEClient` contract above. `UEClient` prepares and executes the project; it is
not a dependency inside the generated Unreal module.
