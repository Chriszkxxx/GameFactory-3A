# three_js/import_generated/

The bridge from what `models/` produced to something a three.js runtime
can actually use.

## Why this is thinner than the UE5 equivalent

Unreal must *import* a source mesh: run Interchange, build a
`StaticMesh`/`SkeletalMesh` uasset, generate collision, and cook. The web
has no import step — a `.glb` file **is** the runtime format. Staging it
is a file copy, which the adapter already performs in
`assets/_internal/service.py`.

What the web still needs is proof the file will load and the same
triangle/material/animation/bounds numbers the pipeline records. That is
what `import_mesh.mjs` produces, using the exact `GLTFLoader` the game
will use at runtime.

| Path | Runs where |
| --- | --- |
| `import_mesh.mjs` | host Node, with the project's `three` installed |
| `engine_adapters/three_js/assets/_internal/inspectors.py` | host Python, no Node required |
| `scripts/import_generated_asset.py` | host Python — finds the toolchain, launches the importer, reads its JSON report |

Two inspectors exist on purpose. The Python one parses the glTF container
directly so validation works with no Node process at all; the Node one
proves the real loader accepts the file. Validation gates use the first;
release evidence uses the second.

## Usage

```bash
node engine_adapters/three_js/import_generated/import_mesh.mjs \
    --source test_data/outputs/<game>/<run>/3d_object/<task>/mesh.glb \
    --usage asset \
    --report .a3game/reports/import-mesh.json
```

Usage tiers match the other engines — `asset`, `vfx_standalone`,
`vfx_particle` — and each carries a triangle, texture, and byte budget.
Exceeding the triangle budget fails; exceeding textures or bytes warns.

## Report shape

```json
{
  "ok": true,
  "operation": "import_generated.import_mesh",
  "errors": [],
  "warnings": [],
  "payload": {
    "source": "...", "asset_name": "mesh", "usage": "asset",
    "bytes": 1048576, "meshes": 3, "skinnedMeshes": 1,
    "triangles": 41280, "materialCount": 2, "textureCount": 5,
    "animationCount": 4, "animations": ["idle", "walk", "run", "attack"],
    "bounds": { "min": [], "max": [], "size": [], "center": [] }
  }
}
```

## Prerequisites

- Node 20 or newer;
- `three` installed in the project — call
  `ThreeClient.project.install_dependencies()` first;
- Draco-compressed files additionally need `--draco-decoder <dir>`
  pointing at the decoder directory that is served at `/draco/` at
  runtime.

## What does not belong here

Do not stage files, write the asset manifest, or register artifacts from
this script. Those are owned by the public `ThreeClient.assets.*`
namespace so the registry stays the single source of truth.
