# Unity API Context

For smoke, fire, explosion, dust, and particle lifecycle work, use the
[`create-vfx-effects`](create-vfx-effects/SKILL.md) skill and
`engine_adapters/unity3d/vfx/Runtime/A3Game_VFX.cs`.

Prefer an existing reviewed particle or VFX Graph prefab through `SpawnPrefab`.
The named ParticleSystem functions are no-asset fallbacks. Their positions use
Unity world-space meters.

The procedural style fallbacks are `SpawnInkSmoke`, `SpawnFrostFire`, and
`SpawnCyberFire`. Prefer authored prefabs when available; the style functions are
layered fallbacks and still require visual approval.

## Import Generated Meshes

Use the host launcher for generated GLB, FBX, or OBJ files:

```bash
python scripts/import_generated_asset.py --engine unity \
    --src <model> --unity-project <project>
```

The launcher installs
`engine_adapters/unity3d/import_generated/ImportGeneratedMesh.cs` under the
project's `Assets/Editor/` directory and invokes `ImportGeneratedMesh.RunFromCLI`.
Use `--usage asset` for ordinary meshes, `vfx_standalone` for a single effect
mesh, and `vfx_particle` for meshes instanced by a particle system.

Treat the JSON import report as the result contract. Check `ok`, `assetPath`,
`prefabPath`, triangle and material counts, bound textures, bounds, and warnings
before referencing the prefab. GLB import requires `com.unity.cloud.gltfast`;
the full project setup is in `scripts/installing/engine_import_setup.md`.
