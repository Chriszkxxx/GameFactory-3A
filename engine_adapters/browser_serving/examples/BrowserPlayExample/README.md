# Browser Play Example

This is the reference for the final delivery stage after an upstream assembly
step has:

1. generated the Mechanic and native UI plugins;
2. assembled them into one native Engine project or runtime artifact;
3. imported the selected assets and built the world;
4. compiled and validated the native project.

The Example does not build gameplay, import assets, compile an Engine project,
or implement a Browser Serving backend. It demonstrates the remaining handoff:

```text
prepared native project plus registered Engine backend
  -> Browser Serving Gateway
  -> Engine runtime session
  -> stream_url
  -> task-owned /game browser page
```

Values such as `selected_by_packet` in the reference manifest are placeholders.
Generated output must replace them with the canonical Engine and registered
backend values from its prepared packet.

## Run

Configure the selected Engine backend through the Pipeline or operator, then
run `launch.cmd`.

The launcher mounts this directory through `A3GAME_BROWSER_PLAY_DIR` and starts
the public Gateway entry point. Open:

```text
http://127.0.0.1:7870/game/
```

The page health-checks Browser Serving, recovers a session when one is supplied
or stored, otherwise creates a new session for the selected Engine, and
presents the returned `stream_url` in a full-page frame. The streamed Engine
frame already contains the native gameplay UI.

Run the static contract test with:

```text
node tests/browser_play.test.js
```
