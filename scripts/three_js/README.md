# three.js Scripts

These launchers are thin wrappers around the public
`ThreeClient(api_version="v1")` API.

Python implementation lives in `engine_adapters/three_js/cli.py`:

```text
scripts/three_js/*.sh or *.cmd -> engine_adapters.three_js.cli -> ThreeClient
```

## Toolchain

Unlike Unreal, the three.js adapter has no engine installation. Its only
external requirement is a **Node 20+** toolchain on `PATH`, because the
adapter drives `vite`, `vitest`, and the package manager through its
private Node transport.

`setup_env.sh` provisions that toolchain as a conda environment, so a
machine with no system Node still works:

```bash
scripts/three_js/setup_env.sh                # create or verify the env
scripts/three_js/setup_env.sh --force# recreate from scratch
scripts/three_js/setup_env.sh --print-activate # just show the two commands
```

Activate it in any shell before using the other scripts:

```bash
source <conda_root>/etc/profile.d/conda.sh
conda activate threejs
```

| Variable | Meaning | Default |
|---|---|---|
| `A3GAME_CONDA_ROOT` | conda installation prefix | `$CONDA_EXE` prefix, then `~/miniconda3`, `~/anaconda3`, `/opt/conda` |
| `A3GAME_THREE_CONDA_ENV` | environment name | `threejs` |
| `A3GAME_NODE_VERSION` | Node spec passed to conda | `20.*` |
| `A3GAME_PYTHON` | interpreter used to import the adapter | `python3` |

Validated baseline: three.js r185 (`three@0.185.0`), Node 20, Vite 6.

## Create a project

`create-project` scaffolds a Vite + three.js host project, installs the
adapter-owned `A3GamePlayable` framework as `@a3game/playable`, and runs
the package manager. It installs **no** gameplay.

```bash
scripts/three_js/create_project.sh \
  --project-path /path/to/GeneratedGame \
  --dev-port 5173

# scaffold only, no npm install and no framework copy
scripts/three_js/create_project.sh \
  --project-path /path/to/GeneratedGame \
  --skip-install --skip-framework
```

## Import an asset

Asset import accepts repository task identities, not arbitrary source
paths. It stages the file under `public/`, records an artifact, and
rewrites `public/assets/manifest.json`.

```bash
scripts/three_js/import_asset.sh \
  --project /path/to/GeneratedGame/package.json \
  --game-id gameA_cyberpunk_shooter \
  --task-id cyberpunk_sword_001 \
  --type prop \
  --artifact-key glb_path
```

`--type scene` routes to `three.world.build` and publishes a runtime
scene graph under `public/assets/worlds/` instead of staging a mesh.

## Where art comes from

Not a launcher: acquiring content is an operator concern, so both paths
live in `operators/gen_3d_object/funcs/` and are called from Python.

```python
# Three CC0 models, seconds, no GPU — when generating is overkill.
from operators.gen_3d_object.funcs import fetch_asset_pack
fetch_asset_pack(games=["game_archer_explorer"])

# The props a particular game actually needed.
from models.gen_3d_object.trellis_2_model import Trellis2Model
from operators.gen_3d_object.operator import Gen3DObjectOperator
op = Gen3DObjectOperator(model=Trellis2Model(model_path="…/TRELLIS.2-4B"))
op.run_art_plan("game_archer_explorer", image_model=…)
```

Both end identically: an asset task output, a public
`ThreeClient.assets` import that declares the facing axis and the height
in metres, and a review sheet. Neither copies a file into `public/`.

Set `https_proxy` if the download needs one.

## Run the dev server

```bash
scripts/three_js/run.sh --project /path/to/GeneratedGame/package.json
scripts/three_js/run.sh --project /path/to/GeneratedGame/package.json --wait-only
```

The server binds `127.0.0.1` by default, so nothing outside the machine
can see it. To play a game hosted on a remote dev box:

```bash
scripts/three_js/run.sh --project /path/to/package.json --dev-host 0.0.0.0
```

Then either forward the port — `ssh -N -L 5173:127.0.0.1:5173
<user>@<server>` and open `http://127.0.0.1:5173/` — or, if the port is
reachable, open `http://<server_ip>:5173/` directly. WebGL renders in the
viewer's browser, so the server needs neither GPU nor display.

Platform gateway and browser serving are not started by these scripts.

## Boundaries

These launchers only call public namespaces. They never touch
`engine_adapters.three_js._internal`, never run bare `npm` commands
against a project, and never write into a generated project's
`packages/` tree — `three.plugin.install` owns that.
