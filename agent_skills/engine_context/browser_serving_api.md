# Browser Serving Agent API Reference

Status: implemented Browser Serving API `v1`.

## Hard Boundary

Browser Serving is an engine-agnostic mapping layer:

```text
Browser UI -> Browser Serving API -> EngineBackend -> Engine
```

It maps engine view, assets, Worlds, sessions, preview, Play, stream, and
generic input to Web. It does not replace the engine-native Mechanic UI.

`UE5ExampleBackend` is only the first backend example. Browser Serving is not
UE Serving.

The UE example may access Unreal only through:

```python
from engine_adapters.ue5 import UEClient
```

Browser UI must not import a concrete engine backend or branch on engine names.

## Result Contract

Public operations return:

- `ok` - operation success;
- `operation` - stable operation name;
- `engine` - selected backend id;
- `artifacts` - produced or inspected assets;
- `warnings` - non-fatal diagnostics;
- `errors` - fatal diagnostics;
- `payload` - operation-specific data.

## Public Entry Point

- `BrowserServingClient` - Python client for the public HTTP API.
- `BrowserServingConfig` - Resolves Gateway, Admin, upload, stream, session,
  and backend configuration.
- `BrowserServingService` - Delegates public operations to a registered
  backend.
- `EngineBackend` - Contract implemented by engine backends.
- `EngineCapabilities` - Declares supported browser-facing capabilities.
- `EngineDescriptor` - Describes one registered backend.
- `AssetImportRequest` - Carries a staged file and task descriptor to a
  backend.
- `AssetRecord` - Engine-neutral imported asset record.
- `WorldRecord` - Engine-neutral runtime World record.
- `create_app` - Creates the Browser Serving FastAPI Gateway.

## BrowserServingClient

- `client.health` - Reports API readiness and registered engines.
- `client.engines` - Lists engine descriptors and capabilities.
- `client.engine_status` - Reports readiness for one backend.

## Assets

- `client.assets.upload` - Uploads a file, stages it as a standard
  AAAGameForge task artifact, and imports it through the selected backend.
- `client.assets.import_descriptor` - Imports an existing generated task
  artifact.
- `client.assets.list` - Lists backend-visible assets.
- `client.assets.groups` - Groups Avatar, Skeleton, Motion, environment, prop,
  weapon, effect, material, and texture assets.
- `client.assets.inspect` - Inspects one imported artifact.

Routes:

```text
POST /api/assets/upload
POST /api/assets/import
POST /api/assets/inspect
GET  /api/assets
GET  /api/assets/groups
```

Uploads are staged through `pipeline.common.paths`. The UE example receives a
generated task descriptor through `UEClient`, not an arbitrary browser path.

Use `artifact_id` for cross-engine session selection. `native.path` is
backend metadata.

## Worlds

- `client.worlds.upload` - Uploads a Scene and invokes backend World
  build/publish.
- `client.worlds.list` - Lists runtime World packages.

Route:

```text
GET /api/worlds
```

Scene upload uses `POST /api/assets/upload` with `asset_type=scene`.

## Sessions

- `client.sessions.create` - Starts one browser-owned engine/stream session.
- `client.sessions.list` - Lists active sessions.
- `client.sessions.get` - Reads one session.
- `client.sessions.recover` - Re-registers a still-reachable session.
- `client.sessions.catalog` - Lists runtime-ready Avatars, Motions, and Worlds.
- `client.sessions.configure` - Selects Avatar, idle Motion, move Motion, and
  character options.
- `client.sessions.play_preview_animation` - Plays one preview Motion.
- `client.sessions.load_world` - Selects a runtime World.
- `client.sessions.join` - Enters Play mode.
- `client.sessions.leave` - Leaves Play mode.
- `client.sessions.apply_input` - Sends normalized movement/look/run/jump
  input.
- `client.sessions.apply_preview_camera` - Sends preview camera input.
- `client.sessions.stop` - Stops the engine session and stream.

Routes:

```text
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/catalog
POST   /api/sessions/recover
POST   /api/sessions/runtime-event
GET    /api/sessions/{session_id}
POST   /api/sessions/{session_id}/character
POST   /api/sessions/{session_id}/preview-animation
POST   /api/sessions/{session_id}/load-world
POST   /api/sessions/{session_id}/join
POST   /api/sessions/{session_id}/leave
POST   /api/sessions/{session_id}/input
POST   /api/sessions/{session_id}/preview-camera
DELETE /api/sessions/{session_id}
```

WebSocket:

```text
WS /api/sessions/{session_id}/input-ws
```

Normalized input supports movement, look, run, jump, sequence, and timestamp.
Game-specific actions remain owned by the Mechanic contract.

## Engine Discovery

- `GET /api/health` - Reports API readiness.
- `GET /api/engines` - Lists registered backends.
- `GET /api/engines/{engine}/capabilities` - Reports backend capabilities.
- `GET /api/engines/{engine}/status` - Reports backend readiness.

UI must enable controls from capabilities, not from engine-name checks.

`streaming` is the engine-neutral capability for a backend that can return a
browser-embeddable `stream_url`. `pixel_streaming` remains a UE compatibility
capability and must not be required from future non-UE backends.

## EngineBackend Contract

- `descriptor` - Returns id, display name, API version, and capabilities.
- `status` - Reports backend readiness.
- `import_asset` - Imports a staged asset.
- `inspect_asset` - Inspects one asset.
- `list_assets` - Lists assets.
- `list_worlds` - Lists runtime Worlds.
- `build_world` - Builds or publishes a World.
- `create_session` - Creates an engine/browser session.
- `list_sessions` - Lists sessions.
- `get_session` - Reads one session.
- `recover_session` - Recovers one session.
- `session_catalog` - Lists runtime-ready assets and Worlds.
- `configure_session` - Configures the session character.
- `play_preview_animation` - Plays a preview animation.
- `load_world` - Selects a World.
- `join_world` - Enters Play mode.
- `leave_world` - Leaves Play mode.
- `apply_input` - Applies normalized input.
- `apply_preview_camera` - Applies preview camera input.
- `handle_runtime_event` - Applies engine readiness/runtime events.
- `stop_session` - Stops one session.
- `debug` - Supports migrated developer controls without exposing engine
  internals to frontend code.

A streaming backend returns `stream_url` from create, get, and recover session
operations. Transport-specific aliases may also be present, but generated
Browser Play uses `stream_url`.

The engine-neutral session handoff is:

```json
{
  "streaming": true,
  "stream_url": "https://browser-embeddable-session-url"
}
```

`streaming` declares that the selected backend supports browser presentation.
`stream_url` is the URL consumed by generated Browser Play. The current UE
backend may also expose `pixel_streaming` and `pixel_streaming_url` for
compatibility, but those fields are not the cross-Engine contract.

## UE5 Example Backend

Implementation:

```text
engine_adapters/browser_serving/backends/ue5_example.py
```

- `create_ue5_example_backend` - Creates the first example backend.
- `status` - Maps public UE environment status.
- `import_asset` - Maps assets to public `ue.assets`.
- `build_world` - Maps Scenes to public `ue.world`.
- `list_assets` - Maps UE assets to `AssetRecord`.
- `list_worlds` - Maps UE packages to `WorldRecord`.
- `create_session` - Allocates ports and launches signalling plus UE.
- `configure_session` - Maps Avatar/Motion selection to
  `ue.runtime.sessions`.
- `join_world` - Enters the selected Play World.
- `apply_input` - Maps browser input to normalized UE runtime input.
- `stop_session` - Stops UE and Pixel Streaming processes owned by Serving.

This code is a backend example for other engines. Generated browser UI must not
import it.

## Adding Another Backend

1. Add `engine_adapters/browser_serving/backends/<engine>_example.py`.
2. Implement `EngineBackend` with truthful capabilities.
3. Export its factory from `backends/__init__.py`.
4. Register it through `create_app(backends=[backend])`.
5. Add asset, World, session, stream, input, and cleanup tests.
6. Keep the existing 7860/7870 controls and routes unchanged.

Do not change player/admin buttons when adding an engine backend.

## Frontends

- `build_admin_app` - Creates the 7860 asset administration UI.
- `launch_admin` - Runs the 7860 Admin UI.
- `run_gateway` - Runs the 7870 Gateway/player.
- `run_all` - Runs both services.
- `frontend/admin.py` - Upload/import, Avatar/Motion, Scene/World, preview, and
  session controls.
- `frontend/player/viewer.html` - Player window.
- `frontend/player/viewer.js` - Engine discovery, sessions, Play, stream, and
  input behavior.
- `frontend/player/viewer.css` - Player layout.

Generated Browser Play must be directly bootstrappable:

- call `GET /api/health` before session work;
- recover a supplied `session` query parameter when present;
- otherwise create a generic session with `POST /api/sessions`;
- read engine-neutral `stream_url` from the returned session;
- keep keyboard and mouse input inside the streamed Engine frame;
- report session or stream errors instead of showing a false ready state.

The validated engine-neutral Browser Play delivery reference is:

```text
engine_adapters/browser_serving/examples/BrowserPlayExample
```

It demonstrates the task-owned manifest, thin launcher, create-or-recover
session flow, `stream_url` presentation, input focus, fullscreen, and error
recovery without assuming a specific Engine or streaming transport. Generated
UI may adapt that delivery pattern but must not depend on the Example at
runtime.

The generated page does not configure or implement Engine backends. The
Pipeline or operator must mount its directory through
`A3GAME_BROWSER_PLAY_DIR` and configure the packet-selected backend before
launching Browser Serving.

For the current bundled UE 5.4 backend specifically, configure
`A3GAME_UE_PROJECT` and `A3GAME_UE_ROOT`. For its `player.html`, keep
`A3GAME_BROWSER_PIXEL_USE_FRONTEND=0`. Setting it to `1` requires a separately
running Epic Frontend service.

## UIgen Boundary

Engine-runtime UI:

- reads the Pipeline-selected concrete Engine API;
- reads the finalized generated Mechanic contract and Public source;
- selects the minimum useful same-Engine Mechanic and UI reference files under
  the packet-registered roots;
- generates the real engine-native HUD/widgets/menus.

Browser Serving UI:

- uses `api_context_target = browser_serving`;
- reads this Pipeline-selected Browser Serving API;
- maps stream, assets, sessions, preview, Play, and generic controls to Web;
- does not replace or duplicate engine-native Mechanic UI.

The current Browser Serving API does not expose a versioned Mechanic
state/event/command bridge to Web. Do not invent Web health, ammo, score,
objective, pause, victory, or command UI.

## Launch

- `python -m engine_adapters.browser_serving all` - Runs 7860 and 7870.
- `python -m engine_adapters.browser_serving gateway` - Runs 7870 only.
- `python -m engine_adapters.browser_serving admin` - Runs 7860 only.

Port ownership is:

- `7860` - asset administration;
- `7870` - Gateway, API, generic player, and mounted `/game`;
- `18080+` - current UE backend per-session stream pages;
- `18888+` - current UE backend streamer WebSocket ports.

Do not assume `7080`, `8000`, or `8080`. Override the documented environment
variables when those ports are required.

Engine-neutral task-owned Browser Play launch:

```powershell
$env:A3GAME_BROWSER_PLAY_DIR = "D:\path\generated_ui\browser_play"
# Configure the packet-selected Engine backend here.
python -m engine_adapters.browser_serving all
```

Then open `/game` on the Gateway. The page creates a session when no session
query parameter is supplied.

`A3GAME_BROWSER_DRY_RUN=1` validates Serving/frontend lifecycle without real
engine rendering.
