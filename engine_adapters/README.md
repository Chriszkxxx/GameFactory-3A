# engine_adapters/

Engine-side reference code — **fed to the LLM as context** when generating
mechanic / UI code, and used at runtime for RPC-style asset delivery.

## Sub-directories

| Directory   | Contents                                                   |
|-------------|------------------------------------------------------------|
| `ue5/`      | UE5 Blueprint templates, C++ modules, Python-remote scripts, importer helpers |
| `unity3d/`  | Unity3D C# templates, Editor scripts, PackageManager manifests |
| `blender/`  | Blender Python (`bpy`) importers, rig / retarget helpers, headless render scripts |
| `three_js/` | Web preview: glTF loaders, scene scaffolds, HUD overlays |

The LLM is expected to *reference / extend* these files rather than write engine
code from scratch, which improves compile-rate and reduces hallucinated APIs.

## Importing generated assets

Each engine has an `import_generated/` sub-directory: the bridge from what
`models/` produced to something the engine can actually use. It is deliberately
separate from the engine interface functions above — one is "how the engine
does X", the other is "how our artifacts get in".

| Path | Runs where |
|------|-----------|
| `ue5/import_generated/import_mesh.py` | Unreal's Python |
| `unity3d/import_generated/ImportGeneratedMesh.cs` | Unity Editor (`Assets/Editor/`) |
| `scripts/import_generated_asset.py` | host Python — finds the editor, launches either importer, reads its JSON report |

```bash
python scripts/import_generated_asset.py --engine both \
    --summary test_data/outputs/<game>/<run>/3d_object_results_summary.json
```

Both importers take the same `--usage {asset,vfx_standalone,vfx_particle}` tier
and write a JSON report (asset path, triangles, bounds, materials, warnings), so
"the chain works" is checkable instead of assumed. See each directory's README.

Prerequisites: Unity needs `com.unity.cloud.gltfast` in the project; UE needs the
`PythonScriptPlugin` enabled, and is driven through the full editor rather than a
commandlet (the UE README explains why).

Per-engine API notes that go straight into the agent's context live separately in
`agent_skills/engine_context/{ue5,unity3d,blender,three_js}_api.md`.
