# engine_adapters/

Engine-side reference code — **fed to the LLM as context** when generating
mechanic / UI code, and used at runtime for RPC-style asset delivery.

## Sub-directories

| Directory   | Contents                                                   |
|-------------|------------------------------------------------------------|
| `ue5/`      | UEClient, private transports/importers, Automation testing, AAAGamePlayable, Preview, reference gameplay plugins |
| `unity3d/`  | Unity3D C# templates, Editor scripts, PackageManager manifests |
| `blender/`  | Blender Python (`bpy`) importers, rig / retarget helpers, headless render scripts |
| `three_js/` | Web preview: glTF loaders, scene scaffolds, HUD overlays |

The LLM is expected to *reference / extend* these files rather than write engine
code from scratch, which improves compile-rate and reduces hallucinated APIs.

Per-engine API notes that go straight into the agent's context live separately in
`agent_skills/engine_context/{ue5,unity3d,blender,three_js}_api.md`.

Repository launchers live under `scripts/<engine>/`. For UE5,
`scripts/ue/*.cmd` and `scripts/ue/*.sh` call
`engine_adapters.ue5.cli`, whose implementation uses only the public
`UEClient` facade.
