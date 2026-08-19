# Code Generation Architecture (supplement to setting_overview.md)

> Insert this section after "## Three different kinds of agent work" and before
> "## Runnable counterparts" in `agent_skills/setting_overview.md`.

## Code generation pipeline

When an agent generates game code (mechanic or UI), these architecture rules
are mandatory. Detailed workflows belong in the Skill documents
(`code_gen/mechanic/game_generation.md`, `code_gen/ui/game_ui_generation.md`),
not here.

### Dependency direction

```
Task Packet → Mechanic Generation → UI Generation → Execution/Assembly → Browser Serving
```

Mechanic is generated first. UI consumes the finalized Mechanic contract.
Browser Serving maps the built Engine runtime into a browser — it is not a
second gameplay runtime.

### Layer ownership

| Layer | Owns | Must not own |
|---|---|---|
| Mechanic | gameplay rules, state, events, commands, native plugin, public contract | HUD, widgets, Browser Play, asset import, builds |
| UI | native UI plugin, contract bindings, HUD/screens, Browser Play delivery | gameplay rules, duplicate state, Engine backend |
| Execution | project prep, asset import, plugin install, build, tests, launch | generated gameplay, private Engine internals |
| Browser Serving | browser session, stream URL, generic input, backend lifecycle | Mechanic rules, native HUD, game-specific browser commands |

### Client-only engine operations

All host-side Engine operations must use the selected public Engine Client:

```
UE5     → from engine_adapters.ue5 import UEClient
Unity3D → from engine_adapters.unity3d import UnityClient
Three.js → from engine_adapters.three_js import ThreeClient
```

Do not call `UnrealEditor`, `Build.bat`, `AssetTools`, `bpy`, private transports,
or adapter internals directly. If a required operation is not exposed publicly,
report an API gap rather than creating a parallel path.

### Hard failure conditions

An implementation is invalid if:

- Mechanic source includes UMG, Slate, Canvas HUD, or Browser Serving code;
- UI source implements gameplay rules or maintains a second gameplay state;
- A host-side script bypasses the selected public Engine Client;
- Browser Play imports a concrete backend or calls an Engine Client directly;
- An Engine Example is copied as a runtime dependency into a generated project.

### Task routing

| Task | Read |
|---|---|
| Mechanic generation | `code_gen/mechanic/game_generation.md` + `engine_context/<engine>_api.md` |
| UI generation | `code_gen/ui/game_ui_generation.md` + `engine_context/<engine>_api.md` + `engine_context/browser_serving_api.md` |
| Framework development | `develop_harness/README.md` |
| Art review | `asset_qa/` |
