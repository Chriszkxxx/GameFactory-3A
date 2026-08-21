# Godot Agent API Reference

Status: implemented `GodotClient` API version `v1` for Godot 4.x.

This file is the compact public capability index. Read public method source for
exact optional parameters and payload details.

## Hard API boundary

The only supported host entry point is:

```text
from engine_adapters.godot import GodotClient
```

Generated native code may use the installed project add-on at:

```text
res://addons/a3game_playable/
```

Do not import `engine_adapters.godot._internal`, invoke Godot binaries outside
the Client, construct output paths manually, edit the adapter-owned runtime, or
depend on `engine_adapters/godot/examples/` at runtime. Generated mechanic and UI
code belongs in a separate project-local add-on.

## Result contract

Every public operation returns strict-JSON-serializable `ok`, `operation`,
`artifacts`, `diagnostics`, `warnings`, `errors`, and `payload` fields. Public
metadata and persistent registries reject non-standard `NaN` and infinity
values instead of emitting JavaScript-only constants.

## Client and configuration

- `GodotClient` constructs all public namespace clients.
- `godot.api_version` reports `v1`.
- `godot.get_environment_info` reports project, executable, runtime port, and
  registry paths.

Constructor fields are `project_path`, `godot_executable`, `api_version`, and
keyword-only `runtime_host`, `runtime_port`, `editor_timeout`, `import_timeout`.
They resolve from `A3GAME_GODOT_*` variables. If no executable is configured,
the adapter discovers `godot4`, `godot`, or `godot-mono` on `PATH`.
`A3GAME_GODOT_DATA_ROOT`, `A3GAME_GODOT_ARTIFACT_REGISTRY`, and
`A3GAME_GODOT_WORLD_REGISTRY_ROOT` override persistent state locations. Every
existing path component must be an ordinary directory (and every managed leaf
an ordinary file); symbolic links and special nodes fail closed.

## Project

- `godot.project.get_info` reports `project.godot`, main scene, executable, and
  version probe evidence.
- `godot.project.create` creates a minimal Godot 4 project and import roots
  without concrete gameplay.
- `godot.project.validate` checks the marker, main scene, and optional engine
  executable. With engine checks enabled, Godot must load and instantiate the
  resolved main scene as a `PackedScene`; static-only checks still verify text
  scene headers.

`project.godot` is the project identity. Passing a directory and passing its
`project.godot` file are equivalent.

## Assets

- `godot.assets.import_asset` imports a registered task artifact by type.
- `godot.assets.register_resource` adds an existing in-project `res://`
  resource only after Godot 4 loads it and validates its native type and
  spawnability. The resource must be a canonical regular file below the
  project; traversal, symlinks, missing files, and mismatched caller claims are
  structured failures.
- Typed helpers: `import_avatar`, `import_motion`, `import_scene`, `import_prop`,
  `import_weapon`, `import_material`, `import_texture`, `import_effect`, and
  `import_audio`.
- `godot.assets.validate` validates source identity, format, destination, and
  containment without copying.
- `godot.assets.resolve_source` resolves a repository task identity.
- `godot.assets.list` and `list_registered` query imported resources.
- `godot.assets.get_metadata` retrieves one artifact record.

Malformed, unreadable, linked, or special-node artifact registries are reported
as structured operation failures. Registry reads fail closed and never replace
the source registry while reporting the problem.

Public asset calls consume `{game_id, run_id, task_kind, task_id, artifact_key}`
identities. They do not accept arbitrary generated-output paths. Destinations
must be project-relative or `res://` paths without traversal. Every identity is
one path component and the resolved task directory must remain below the
configured `OUTPUT_ROOT`, including after symlink resolution.

The real import lifecycle copies into `res://assets/imported/...`, runs
`godot --headless --path <project> --import`, rejects a non-Godot-4 executable,
nonzero exit, or import/resource corruption, parse, and dependency-image decode
errors reported at zero exit. It then asks Godot to load the resulting resource.
Spawnable assets must instantiate as `PackedScene`; mesh-like assets must contain
a `MeshInstance3D`, while avatars additionally require a skinned mesh and
Skeleton3D bones. Native class and inspection data are recorded rather than
inferred from a filename. Default roots mirror asset types. Prefer GLB/glTF for
meshes and animation;
Godot-version-specific FBX import returns a portability warning. A `.gltf`
import preflights the main resource and every referenced local buffer/image
before copying; without `replace_existing=True`, one conflicting sidecar rejects
the whole import without changing the project. A later native-validation
failure restores the sources, adjacent `.import` metadata, and matching
`.godot/imported` cache files as one transaction.

Bare `.obj` files are rejected for spawnable asset types because Godot 4 loads
them as `ArrayMesh`, while this adapter's runtime contract requires an
instantiable `PackedScene`. Convert them to GLB/glTF or wrap them in a Godot
scene before publication.

## Animation and bindings

- `godot.animation.import_motion` imports motion against a declared Skeleton3D
  NodePath.
- `godot.animation.resolve_skeleton` loads an avatar and resolves live
  Skeleton3D paths with bones.
- `godot.animation.validate_compatibility` reloads a motion and requires an
  animation, a bone-targeted track, and the requested live Skeleton3D path.
- `godot.bindings.bind_pbr_material` imports a StandardMaterial3D or creates a
  `.tres` from an image, runs the adapter-owned Godot SceneTree script, applies
  `material_override` to every target `MeshInstance3D`, saves bound
  `PackedScene` resources, and atomically retargets those artifact records.

The binding manifest under `.a3game/bindings/` is audit metadata, not the
application mechanism. Success requires Godot to report at least one changed
`MeshInstance3D` per target and requires each bound scene file to exist;
otherwise material, scene, manifest, texture, and registry writes roll back.

Generated glTF/GLB/FBX/DAE motion loads as `PackedScene` and is registered as
such. Standalone `AnimationLibrary` or `Animation` resources cannot prove a
live Skeleton3D and are not accepted by this generated-motion import path. The
adapter does not infer or relabel native classes. These checks establish
structural compatibility, not visual retargeting quality.

## World

- `godot.world.build` imports a scene and creates, validates, and optionally
  publishes a World package.
- `godot.world.create_draft`, `validate_draft`, `publish_draft`, and
  `list_packages` own persistent World manifests under `.a3game/worlds/`.

`create_draft(spec, *, draft_id="", project_id="", metadata=None)` accepts the
same public keywords as UE, Unity, and three.js. Non-empty explicit IDs override
the corresponding spec values; explicit metadata is merged over spec metadata.
`list_packages(*, project_id="", world_id="")` filters by either or both IDs.

Published packages point at a ready, spawnable, registered Godot `scene`
record whose `res://` path and `PackedScene` backend class agree. Godot must
also load and instantiate the native resource. Draft creation, validation, and
publication recheck that contract; packages do not duplicate native scene
content.

## Plugin

- `godot.plugin.install` installs a registered generated add-on containing
  `plugin.cfg` under `res://addons/`.
- `godot.plugin.install_framework` installs and enables `A3GamePlayable`.
- `godot.plugin.list` lists installed project add-ons.

The installer rejects traversal and symlinks and will not replace an existing
add-on unless explicitly requested.

## Build and test

- `godot.build.project` requires a named `export_presets.cfg` preset and runs
  `--export-release`, `--export-debug`, or `--export-pack`. It requires the
  requested output to exist after a successful process. Export output is first
  written to an isolated staging directory and committed as a complete sibling
  artifact set, preserving an existing build when Godot fails. Successful
  commits write a signed ownership manifest with content proofs; later builds
  replace only the unchanged, authenticated managed set. The signing key is
  private adapter state under `A3GAME_GODOT_DATA_ROOT` or `<project>/.a3game`.
  Edited manifests, changed/unmanaged outputs or companions, symlinked paths,
  and paths that alias `project.godot`, `export_presets.cfg`, or the signing key
  fail before commit. Directory output trees are inspected recursively and any
  nested symbolic link is rejected, regardless of its target.
- `godot.testing.run_automation_tests` runs the adapter test runner (or an
  explicit SceneTree script), requires a fresh JSON report, and reports matched,
  passed, failed, and skipped counts. Reports are written to a private sibling
  staging path, schema-validated, and atomically published; destinations that
  alias the project file, runner, or native test inputs are rejected.

An explicit runner may be an absolute/relative host path or a project
`res://...` path. Project URIs are passed to Godot unchanged after containment,
existence, and traversal checks.

Native test scripts under `res://tests/` start with `test_`, extend a
constructible Godot type, and expose `run_test() -> bool | Dictionary`. A result
dictionary requires a boolean `ok` and may include `name` and `message`.
Missing or non-boolean `ok` values and all other return types are test failures;
values are never coerced by truthiness. The generation Agent writes tests;
execution/evaluation code owns running them and any success claim.

## Runtime and sessions

- `godot.runtime.launch_editor` / `stop_editor` manage an editor process.
- `godot.runtime.launch_game` / `stop_game` manage a project runtime process.
- `godot.runtime.launch_player` / `stop_player` manage an exported executable.
- `godot.runtime.sessions.join`, `leave`, `heartbeat`, `apply_input`,
  `snapshot`, `reset_world`, and `clear_entity` expose the game-neutral session
  contract.

The same Runtime Client can stop only processes it launched. Native runtime
sessions use the `A3GameRuntime` UDP autoload on port `30050`; an operation
distinguishes local registration from an engine acknowledgement. Browser Web
sessions use iframe/canvas input and do not claim UDP delivery.

An omitted World resolves to `world_001`. `reset_world` removes only that
resolved World's sessions on the client and in the autoload; repeated resets
are idempotent and do not affect other Worlds. `clear_entity` always removes
the matching session. Its `destroy_actor` flag separately controls whether the
autoload invokes the entity's `clear_a3game_entity` hook, so `False` retains the
node while detaching it from runtime control.

When no UDP response arrives, operations may use documented local-only fallback
with a warning (unless `require_runtime=True`). Any received NACK, invalid JSON,
mismatched request/operation, or malformed acknowledgement fails without
changing local session or input state; response fields cannot override the
client's reachability observation.

`A3GameRuntimeEntity` exposes an `a3game_entity_id`, a `runtime_input` signal,
and `apply_a3game_input`. Generated gameplay turns normalized inputs into its
own movement and actions. The framework defines no character, weapon, vehicle,
camera, game rule, or HUD.

The autoload emits `session_joined` only when gameplay must create a node for a
previously absent entity ID. Replacing a participant's controller, or joining
after a controller-only leave while the node remains, emits
`session_reconnected(previous_session, session)` without a synthetic
`session_left` / `session_joined` cycle. Generated gameplay can use
`A3GameRuntime.find_entity(entity_id)` to retrieve that retained node.
`session_left` means control was detached; destroy an entity through
`clear_entity()` or explicit game-owned World cleanup instead.

## Reflection and observation

- `godot.reflection.inspect_artifact` returns registry metadata and optionally
  runs Godot to load a resource, enumerate a PackedScene node tree, and list
  animations.
- `godot.observe.check_status` reports executable, version, project, and
  optional runtime-bridge readiness.

## Browser serving

The registered Godot backend exports or reuses a Web preset, returns the
engine-neutral `stream_url`, and owns its HTTP process lifecycle. Its dedicated
static server emits cross-origin isolation headers, but the engine-neutral
Gateway does not impose COEP on its parent page because existing Unity WebGL
and UE streaming pages may be served from other origins without CORP. The
verified embedded path therefore uses a non-threaded Web preset and does not
claim `SharedArrayBuffer` or cross-origin-isolated iframe support;
threaded/PWA exports are not a verified bundled capability. Configure the
backend with `A3GAME_GODOT_WEB_BUILD` and `A3GAME_GODOT_WEB_PRESET` (default
`Web`).

Godot Web owns keyboard and pointer input inside its iframe canvas. The bundled
backend advertises browser session/stream lifecycle but deliberately advertises
`runtime_character_configuration=false`, `runtime_world_loading=false`, and
`runtime_input=false`: an exported build cannot be rewritten through those
Gateway calls. Unsupported character, animation, World, normalized-input, and
preview-camera calls return explicit failures instead of recording a false
success; configure the Godot project and export again for those changes.

## Coordinate system

Godot 3D is right-handed, Y-up, and uses `-Z` as forward. glTF shares Y-up and
metre units. Keep imported facing/scale metadata explicit; do not add a blanket
axis conversion after Godot's importer has already converted a source format.
