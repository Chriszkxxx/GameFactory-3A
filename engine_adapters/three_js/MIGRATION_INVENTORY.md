# three.js Adapter Migration Inventory

Status: ThreeClient v1, `A3GamePlayable` web Runtime Framework, generated
Gameplay Package installation, world scene-graph publishing, Node
toolchain build and test execution, and the implemented API reference are
complete. Reference Arena Fighter, FPS, and Racing gameplay packages are
extracted. Platform serving, live trace capture, and the bounded repair
coordinator remain, exactly as for the UE5 adapter.

Reference repositories:

```text
refer_code/three_js_corr/three.js    # upstream engine baseline (r185)
refer_code/three_js_corr/ThreeFlow   # Vue3 editor built on three.js
```

Target repository:

```text
my_code/AAAGameForge
```

This inventory maps three.js into the AAAGameForge architecture by
mirroring the UE5 adapter. It does not change the existing Layer A/B/C,
`design_doc.txt`, `pipeline_task.jsonl`, or output layout.

## Design Premise

The UE5 adapter drives an engine that already owns rendering, the world,
the frame loop, input, animation, physics, and an import pipeline. On the
web, three.js is a rendering library only. Reaching UE5 parity therefore
required splitting the work in two:

1. **Python adapter** - the same eleven namespaces as `UEClient`, with
   the same result contract and the same repository task identity
   resolution. This is a strict mirror.
2. **JavaScript runtime framework** - everything Unreal supplies natively
   and three.js does not: a renderer/loop host, an asset resolver, a
   world builder, an input normalizer, an animation director, raycast
   collision primitives, a HUD layer, and a runtime control channel.

Without part 2 there is nothing for a generated game to build on, and
every generated game would re-invent the same 2000 lines. The scaffolding
lives in the framework precisely so it stays game-neutral and testable.

## Namespace Parity

| UE5 | three.js | Same shape? |
| --- | --- | --- |
| `ue.project.*` | `three.project.*` | Yes, plus `install_dependencies` |
| `ue.assets.*` | `three.assets.*` | Yes, plus `import_audio`, `write_manifest` |
| `ue.animation.*` | `three.animation.*` | Yes |
| `ue.bindings.*` | `three.bindings.*` | Yes |
| `ue.world.*` | `three.world.*` | Yes, plus `get_scene_graph` |
| `ue.plugin.*` | `three.plugin.*` | Yes |
| `ue.build.project` | `three.build.project` | Yes |
| `ue.testing.run_automation_tests` | `three.testing.run_automation_tests` | Yes |
| `ue.runtime.launch_editor` | `three.runtime.launch_dev_server` | Renamed; adds `preview_bundle` |
| `ue.runtime.sessions.*` | `three.runtime.sessions.*` | Yes |
| `ue.reflection.*` | `three.reflection.*` | Yes, plus `list_object_names` |
| `ue.observe.check_status` | `three.observe.check_status` | Yes |

## Deliberate Divergences

Each divergence exists because the platform differs, not because the
mirror was incomplete.

| Concern | UE5 | three.js | Why |
| --- | --- | --- | --- |
| Transport | Remote Control HTTP + Python remote execution | Node subprocess + dev server HTTP probe + runtime control channel | A browser cannot host an inbound RPC port |
| Engine root | `ue_root` (installed engine) | `three_root` (optional source checkout) plus `node_modules/three` | three.js is an npm dependency, not an installation |
| Asset import | Interchange builds a uasset | File staging into `public/` | glTF is already the runtime format |
| Asset addressing | `/Game/...` package path | `/assets/...` URL in a manifest | The browser resolves URLs, not packages |
| Map | `.umap` package | `assets/worlds/<id>.json` scene graph | No binary level format exists |
| Framework install | Copy plugin, enable in `.uproject` | Copy package, add `file:` dependency and workspace | npm resolution replaces plugin discovery |
| Build | UnrealBuildTool | `vite build` | — |
| Tests | Automation Test report | vitest or Playwright JSON report | — |
| Extension contracts | `UINTERFACE` | Abstract class plus duck-type validator | JavaScript has no interfaces |
| Components | `UActorComponent` | `object.userData.a3game` slot | three.js has no component system |
| Frame loop | Engine tick | `A3GameRuntimeHost.onTick` | Framework must own `requestAnimationFrame` |
| Physics | Chaos | `A3GameCollisionProbe` raycasts | three.js ships no physics |
| Resource release | Garbage collector | Explicit `dispose()` | WebGL resources are not collected |

## Implementation Progress

Completed:

- established `from engine_adapters.three_js import ThreeClient` as the
  unique public Python entry point with a versioned result contract
  (`ThreeOperationResult`, `ThreeDiagnostic`);
- established `@a3game/playable` as the unique public JavaScript import
  surface for generated gameplay;
- placed the Node toolchain and dev server/runtime transports behind
  `_internal/transport/`;
- reused the repository task identity
  `(game_id, run_id, task_kind, task_id, artifact_key)` for public asset
  resolution, sharing `pipeline.common.paths` and each task's
  `meta.json` with the UE5 adapter;
- implemented a pure-Python glTF/GLB/texture/audio inspector so
  validation, reflection, and metadata need no Node process;
- implemented asset staging, `.gltf` sidecar collection, the artifact
  registry, and the runtime asset manifest;
- implemented PBR material bindings with file-name slot inference,
  consumed at runtime by `A3GameAssetLibrary.applyMaterialBinding`;
- implemented the world spec, draft registry, validation, package
  registry, and runtime scene-graph publishing;
- implemented generated Gameplay Package installation with automatic
  framework synchronization when `@a3game/playable` is declared;
- implemented `vite build` execution with structured diagnostic parsing;
- implemented vitest and Playwright execution that deletes stale reports,
  refuses to score a report older than the run, and fails on a
  zero-match report;
- implemented dev server launch with readiness polling, bundle preview,
  and process ownership limited to processes the client started;
- implemented generic participant, controller, entity, binding, and
  normalized input session state without Fighter/FPS/Racing command
  fields, forwarding each operation to the browser runtime channel and
  reporting delivery separately from bookkeeping;
- implemented `A3GamePlayable` with the data-type contract, three
  extension contracts, two components, two subsystems, and eight engine
  scaffolding modules;
- distilled the reusable three.js patterns from `ThreeFlow`
  (`renderScene`, `sceneModules`, loader map, `disposeScene`,
  `SkeletonUtils.clone`, HDR environment, fog, transform handling) into
  game-neutral framework modules, dropping every Vue, Pinia, Element
  Plus, IndexedDB, and editor-only dependency;
- extracted Arena Fighter, FPS, and Racing reference gameplay packages,
  each owning its concrete entity, factory, rules, and HUD;
- added a reference generated-test suite proving entity, rule, and
  snapshot behavior with no GPU and no screenshots;
- verified the Python chain end to end: project creation, framework
  installation, engine-version detection against the r185 checkout,
  asset inspection and staging, manifest generation, world validation,
  world publishing, and package listing;
- verified the JavaScript chain end to end under Node 20: session
  synchronization, input arbitration and delivery, snapshots, extension
  message dispatch, entity teardown, and factory contract guards.

## Layout

```text
engine_adapters/three_js/
├── __init__.py                  # public entry point: ThreeClient only
├── three_client.py              # facade assembling namespace clients
├── config.py                    # ThreeClientConfig + defaults
├── cli.py                       # create-project / import-asset / run
├── contracts/                   # ThreeOperationResult, ThreeDiagnostic
├── _internal/transport/         # NodeToolchain, DevServerClient
├── project/  assets/  animation/  bindings/  world/
├── plugin/   build/   testing/   runtime/   reflection/  observe/
├── plugin/A3GamePlayable/       # the web Runtime Framework
│   └── src/
│       ├── data-types/          # generic runtime data contract
│       ├── interfaces/          # extension contracts
│       ├── components/          # identity, runtime entity
│       ├── subsystems/          # runtime, world session
│       └── engine/              # host, assets, world, input,
│                                # animation, collision, HUD, channel
├── examples/                    # arena-fighter, fps, racing references
├── import_generated/            # Node-side generated-mesh inspector
└── MIGRATION_INVENTORY.md
```

## Boundary Enforcement

The same rules the UE5 adapter enforces, restated for the web:

- generated gameplay imports `@a3game/playable` and nothing deeper;
- generated gameplay never touches `engine_adapters.three_js._internal`
  or any namespace `_internal` package;
- generated gameplay never hard-codes an asset URL, a `public/` path, or
  a `dist/` path;
- generated gameplay never calls `requestAnimationFrame`;
- the game-generation Agent never invokes `three.testing.*`;
- the example packages are read-only references, never dependencies.

## Remaining Work

- platform serving integration (parity with the UE5 gap);
- live trace and evidence capture through `preview_bundle` plus
  Playwright traces;
- bounded repair coordinator wiring for build and test diagnostics;
- an optional WebSocket relay so `runtime_transport="websocket"` works
  without the local bridge;
- a conforming existing-artifact Evaluator.
