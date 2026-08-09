#!/usr/bin/env python3
"""Stage a curated pack of freely licensed glTF models for the three.js games.

three.js ships **no** 3D models in its npm package — only loaders and
procedural helpers. Good-looking imported content therefore has to come
from somewhere else, and the only sources worth wiring into a repository
are the ones with an unambiguous licence:

* the ``mrdoob/three.js`` example models, and
* ``KhronosGroup/glTF-Sample-Assets``.

This script does two things:

1. downloads each catalogued model into its **own asset task directory**,
   resolved through ``pipeline.common.paths`` — the file plus a
   ``meta.json`` that declares it, which is exactly the "repository task
   identity" the public asset API consumes; and
2. imports it into one or more generated game projects through
   ``ThreeClient.assets``, which stages it under ``public/assets/`` and
   rewrites the runtime manifest.

Nothing here bypasses the adapter: step 2 is theordinary public import
path, and step 1 only produces the kind of task output a real asset
generation task would have produced.

Usage::

    scripts/three_js/fetch_asset_pack.sh                 # everything
    scripts/three_js/fetch_asset_pack.sh --list# show catalogue
    scripts/three_js/fetch_asset_pack.sh --game game_arcade_racer
    scripts/three_js/fetch_asset_pack.sh --no-import     # download only

Set ``https_proxy`` if the network needs one; the download uses the
standard environment proxy configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from engine_adapters.three_js import ThreeClient  # noqa: E402
from pipeline.common import paths  # noqa: E402

THREE_EXAMPLES = (
    "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models"
)
KHRONOS_SAMPLES = (
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets"
    "/main/Models"
)


@dataclass(frozen=True)
class CatalogueEntry:
    """One freely licensed model and the games that use it."""

    asset_id: str
    task_id: str
    file_name: str
    url: str
    asset_type: str
    licence: str
    attribution: str
    summary: str
    animations: tuple[str, ...] = ()
    games: tuple[str, ...] = field(default=())


# Only models whose licence permits redistribution and modification are
# listed, and only models that are actually *game-ready*.
#
# Excluded on licence, having been checked: DamagedHelmet (CC BY-NC), Duck
# (SCEA Shared Source), Sponza (CryEngine licence), and the Mixamo-derived
# characters in the three.js examples, whose terms do not travel with the
# file.
#
# Excluded on suitability, which matters just as much:
#
# * Lantern (9.2 MB) and AntiqueCamera (17 MB) — PBR showcase pieces with
#   4K texture sets. As a prop that occupies fifty pixels, the cost is all
#   download and no visible gain.
#
# And one accepted with a caveat: ToyCar is a single fused mesh, so its
# wheels cannot articulate. It is staged as trackside scenery rather than
# as a drivable car, because a car whose wheels do not turn looks worse
# than a bevelled primitive whose wheels do.
#
# The lesson: "photoreal showcase asset" and "good game asset" are
# different things. File size is the cheapest signal of which one is on
# offer; the node hierarchy is the next cheapest, because a model with no
# separate parts cannot be animated by gameplay.
CATALOGUE: tuple[CatalogueEntry, ...] = (
    CatalogueEntry(
        asset_id="robot_expressive",
        task_id="asset-robot-expressive",
        file_name="RobotExpressive.glb",
        url=f"{THREE_EXAMPLES}/gltf/RobotExpressive/RobotExpressive.glb",
        asset_type="avatar",
        licence="CC0-1.0",
        attribution=(
            "Robot Expressive by Tomas Laulhe (quaternius), CC0 1.0. "
            "Modifications by Don McCurdy."
        ),
        summary=(
            "Rigged, expressive humanoid robot with a full locomotion and "
            "reaction animation set. 456 KB."
        ),
        animations=(
            "Dance", "Death", "Idle", "Jump", "No", "Punch", "Running",
            "Sitting", "Standing", "ThumbsUp", "Walking", "WalkJump",
            "Wave", "Yes",
        ),
        games=(
            "game_fps_pistol_arena",
            "game_sidescroll_brawler",
            "game_archer_explorer",
        ),
    ),
    CatalogueEntry(
        asset_id="fox",
        task_id="asset-fox",
        file_name="Fox.glb",
        url=f"{KHRONOS_SAMPLES}/Fox/glTF-Binary/Fox.glb",
        asset_type="prop",
        licence="CC0-1.0 (model), CC-BY-4.0 (rig and animation)",
        attribution=(
            "Fox by PixelMannen, CC0 1.0. Rigging and animation by "
            "tomkranis, CC BY 4.0. glTF conversion by @AsoboStudio and "
            "@scurest, CC BY 4.0."
        ),
        summary="Low-poly rigged fox with Survey, Walk and Run cycles. 160 KB.",
        animations=("Survey", "Walk", "Run"),
        games=("game_archer_explorer",),
    ),
    CatalogueEntry(
        asset_id="toy_car",
        task_id="asset-toy-car",
        file_name="ToyCar.glb",
        url=f"{KHRONOS_SAMPLES}/ToyCar/glTF-Binary/ToyCar.glb",
        asset_type="prop",
        licence="CC0-1.0",
        attribution="Toy Car, Public domain (CC0 1.0), Khronos Group.",
        summary=(
            "Physically based car with clearcoat paint and glass. 5.4 MB, "
            "authored at 1/10000 scale. Used as trackside scenery, not as a "
            "drivable car: body and wheels are one fused mesh, so nothing "
            "can steer or spin."
        ),
        games=("game_arcade_racer",),
    ),
)

GAME_PROJECTS = {
    "game_fps_pistol_arena": "mechanic/fps-pistol-arena-001",
    "game_sidescroll_brawler": "mechanic/sidescroll-brawler-001",
    "game_arcade_racer": "mechanic/arcade-racer-001",
    "game_archer_explorer": "mechanic/archer-explorer-001",
}


def download(url: str, destination: Path, *, force: bool = False) -> Path:
    """Fetch ``url`` into the cache, reusing an existing copy."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0 and not force:
        return destination
    request = urllib.request.Request(
        url, headers={"User-Agent": "AAAGameForge-asset-fetch/1"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = response.read()
    if not payload:
        raise RuntimeError(f"Downloaded nothing from {url}")
    destination.write_bytes(payload)
    return destination


def stage_source_task(
    entry: CatalogueEntry,
    game_id: str,
    cached: Path,
    *,
    run_id: str,
) -> dict[str, str]:
    """Write the asset task directory that the public API resolves."""

    task_dir = paths.task_output_dir(
        game_id, "3d_object", entry.task_id, run_id=run_id
    )
    target = task_dir / entry.file_name
    if not target.is_file() or target.stat().st_size != cached.stat().st_size:
        shutil.copyfile(cached, target)

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (task_dir / "ATTRIBUTION.md").write_text(
        f"# {entry.asset_id}\n\n"
        f"{entry.summary}\n\n"
        f"- Source: {entry.url}\n"
        f"- Licence: {entry.licence}\n"
        f"- Attribution: {entry.attribution}\n",
        encoding="utf-8",
    )
    paths.write_task_meta(
        task_dir,
        {
            "game_id": game_id,
            "run_id": run_id,
            "task_kind": "3d_object",
            "task_id": entry.task_id,
            "glb_path": entry.file_name,
            "asset_id": entry.asset_id,
            "asset_type": entry.asset_type,
            "source_url": entry.url,
            "licence": entry.licence,
            "attribution": entry.attribution,
            "animation_names": list(entry.animations),
            "sha256": digest,
            "bytes": target.stat().st_size,
            "attribution_file": "ATTRIBUTION.md",
            "generator": "scripts/three_js/fetch_asset_pack.py",
        },
    )
    return {
        "game_id": game_id,
        "run_id": run_id,
        "task_kind": "3d_object",
        "task_id": entry.task_id,
        "artifact_key": "glb_path",
    }


def import_into_project(
    entry: CatalogueEntry, descriptor: dict[str, str], project: Path
) -> dict:
    """Stage the asset into one game project through the public API."""

    client = ThreeClient(project_path=str(project))
    importer = {
        "avatar": client.assets.import_avatar,
        "prop": client.assets.import_prop,
        "weapon": client.assets.import_weapon,
        "scene": client.assets.import_scene,
    }[entry.asset_type]
    return importer(
        descriptor,
        options={"asset_id": entry.asset_id, "replace_existing": True},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--run-id", default=paths.DEFAULT_RUN_ID)
    parser.add_argument(
        "--cache-dir",
        default=str(REPOSITORY_ROOT / "test_data" / ".asset_cache"),
    )
    parser.add_argument("--no-import", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for entry in CATALOGUE:
            print(f"{entry.asset_id:20s} {entry.licence}")
            print(f"  {entry.summary}")
            print(f"  type={entry.asset_type} games={', '.join(entry.games)}")
            if entry.animations:
                print(f"  animations={', '.join(entry.animations)}")
        return 0

    cache = Path(args.cache_dir).expanduser().resolve()
    failures: list[str] = []
    for entry in CATALOGUE:
        if args.asset and entry.asset_id not in args.asset:
            continue
        games = [g for g in entry.games if not args.game or g in args.game]
        if not games:
            continue
        try:
            cached = download(
                entry.url, cache / entry.file_name, force=args.force
            )
        except Exception as exc:  # network or upstream layout change
            failures.append(f"download {entry.asset_id}: {exc}")
            continue
        print(f"{entry.asset_id}: {cached.stat().st_size} bytes cached")

        for game_id in games:
            descriptor = stage_source_task(
                entry, game_id, cached, run_id=args.run_id
            )
            print(f"  staged source task for {game_id}/{entry.task_id}")
            if args.no_import:
                continue
            relative = GAME_PROJECTS.get(game_id)
            if not relative:
                failures.append(f"no project mapping for {game_id}")
                continue
            project = (
                paths.run_dir(game_id, args.run_id)
                / relative
                / "package.json"
            )
            if not project.is_file():
                failures.append(f"project is missing: {project}")
                continue
            result = import_into_project(entry, descriptor, project)
            if not result.get("ok"):
                failures.append(
                    f"import {entry.asset_id} into {game_id}: "
                    f"{result.get('errors')}"
                )
                continue
            staged = result["payload"].get("backend_path", "?")
            print(f"  imported into {game_id} as {staged}")

    for failure in failures:
        print(f"FAILED: {failure}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
