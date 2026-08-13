#!/usr/bin/env python3
"""
scripts/import_generated_asset.py

Host-side launcher for the last leg of the chain:

    models/gen_3d_object  →  test_data/outputs/.../model.glb  →  UE5 / Unity / Blender asset

It finds the engine binary, drives it in batch mode with the importer that lives
in `engine_adapters/<engine>/import_generated/`, and reports what the engine
said. The engine-side scripts are the contract; this file only launches them.

Blender is in the list for a different reason than the other two: it is not a
target, it is the neutral step that reads what a game engine will not (`.ply`,
`.usd`), conditions the asset and writes back the `.glb` UE5 and Unity want. It
is also the only one of the three that needs no project.

Nothing here constructs an output path — sources come from a `--src` or from the
`<kind>_results_summary.json` that `pipeline/assets_gen/gen_3d_object/run.py`
wrote through `pipeline/common/paths.py`.

Usage:
    # validate the artifact and print the exact commands, without an engine
    python scripts/import_generated_asset.py --src out/model.glb --engine both --dry-run

    # Unity (installs the Editor script into the project on first run)
    python scripts/import_generated_asset.py --src out/model.glb \\
        --engine unity --unity-project D:/proj/MyGame

    # UE5 (launches the full editor by default; see --ue-mode)
    python scripts/import_generated_asset.py --src out/model.glb \\
        --engine ue5 --uproject D:/proj/MyGame/MyGame.uproject

    # Blender: condition the asset and write a preview, no project needed
    python scripts/import_generated_asset.py --src out/world.glb \\
        --engine blender --blender-preview

    # everything a generation run produced
    python scripts/import_generated_asset.py --engine both \\
        --summary test_data/outputs/<game>/<run>/3d_object_results_summary.json

Environment (so the flags can be omitted):
    AAAGF_UE_EDITOR       path to UnrealEditor-Cmd.exe
    AAAGF_UPROJECT        path to the .uproject
    AAAGF_UNITY           path to Unity.exe
    AAAGF_UNITY_PROJECT   path to the Unity project root
    AAAGF_BLENDER         path to blender(.exe), or a python that can import bpy
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from models.common.glb_utils import glb_summary  # noqa: E402

try:
    from models.common import ply_utils  # noqa: E402
except ImportError:  # pragma: no cover - optional helper, not always present
    ply_utils = None  # type: ignore[assignment]

UE_IMPORTER = _REPO_ROOT / "engine_adapters" / "ue5" / "import_generated" / "import_mesh.py"
UE_MOTION_IMPORTER = (
    _REPO_ROOT / "engine_adapters" / "ue5" / "import_generated" / "import_motion.py"
)
UNITY_IMPORTER = (_REPO_ROOT / "engine_adapters" / "unity3d" / "import_generated"
                  / "ImportGeneratedMesh.cs")
BLENDER_IMPORTER = (_REPO_ROOT / "engine_adapters" / "blender" / "import_generated"
                    / "import_mesh.py")
BLENDER_MOTION_IMPORTER = (
    _REPO_ROOT / "engine_adapters" / "blender" / "import_generated" / "import_motion.py"
)

USAGES = ("asset", "vfx_standalone", "vfx_particle", "motion")
KINDS = ("mesh", "motion")

#: `both` predates the Blender route and still means the two game engines.
ENGINE_SETS = {"both": ["ue5", "unity"], "all": ["ue5", "unity", "blender"]}


# ── Engine discovery ──────────────────────────────────────────────────────────


def find_unreal_editor(explicit: Optional[str] = None) -> Optional[Path]:
    """
    Locate `UnrealEditor-Cmd`; newest version wins.

    A pointer to `UnrealEditor.exe` is accepted and rewritten to the `-Cmd`
    variant next to it, which is the one that runs commandlets without opening
    a window.
    """
    if explicit or os.environ.get("AAAGF_UE_EDITOR"):
        return _prefer_cmd_binary(Path(explicit or os.environ["AAAGF_UE_EDITOR"]))

    if platform.system() == "Windows":
        # Engines are installed anywhere: the Epic default, or a bare UE_5.x on
        # whatever drive had room.
        patterns = [r"C:\Program Files\Epic Games\UE_*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"]
        patterns += [f"{d}:/UE_*/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
                     for d in "CDEFG"]
        patterns += [f"{d}:/Epic Games/UE_*/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
                     for d in "CDEFG"]
    elif platform.system() == "Darwin":
        patterns = ["/Users/Shared/Epic Games/UE_*/Engine/Binaries/Mac/UnrealEditor-Cmd"]
    else:
        patterns = [str(Path.home() / "UnrealEngine" / "*" / "Engine" / "Binaries"
                        / "Linux" / "UnrealEditor-Cmd")]

    found = sorted(p for pattern in patterns for p in glob.glob(pattern))
    return Path(found[-1]) if found else None


def _prefer_cmd_binary(path: Path) -> Path:
    """`UnrealEditor.exe` → `UnrealEditor-Cmd.exe` when that one exists."""
    if path.stem.endswith("-Cmd"):
        return path
    cmd = path.with_name(path.stem + "-Cmd" + path.suffix)
    return cmd if cmd.exists() else path


def find_unity(explicit: Optional[str] = None) -> Optional[Path]:
    """Locate a Unity editor binary; newest installed version wins."""
    if explicit:
        return Path(explicit)
    if os.environ.get("AAAGF_UNITY"):
        return Path(os.environ["AAAGF_UNITY"])

    patterns = {
        "Windows": [r"C:\Program Files\Unity\Hub\Editor\*\Editor\Unity.exe"],
        "Darwin": ["/Applications/Unity/Hub/Editor/*/Unity.app/Contents/MacOS/Unity"],
        "Linux": [str(Path.home() / "Unity" / "Hub" / "Editor" / "*" / "Editor" / "Unity")],
    }.get(platform.system(), [])
    found = sorted(p for pattern in patterns for p in glob.glob(pattern))
    return Path(found[-1]) if found else None


def find_blender(explicit: Optional[str] = None) -> Optional[Path]:
    """
    Locate something that can run `bpy`; newest installed Blender wins.

    Two things qualify and the importer runs identically under both: a Blender
    application, and a Python whose environment has the pip `bpy` wheel. The
    second is what a headless install script leaves behind, so this interpreter
    is checked before giving up.
    """
    if explicit or os.environ.get("AAAGF_BLENDER"):
        return Path(explicit or os.environ["AAAGF_BLENDER"])

    on_path = shutil.which("blender")
    if on_path:
        return Path(on_path)

    if platform.system() == "Windows":
        patterns = [r"C:\Program Files\Blender Foundation\Blender *\blender.exe"]
    elif platform.system() == "Darwin":
        patterns = ["/Applications/Blender.app/Contents/MacOS/Blender"]
    else:
        patterns = ["/usr/share/blender/*/blender",
                    str(Path.home() / "blender-*" / "blender")]
    found = sorted(p for pattern in patterns for p in glob.glob(pattern))
    if found:
        return Path(found[-1])

    if importlib.util.find_spec("bpy") is not None:
        return Path(sys.executable)
    return None


def is_blender_app(binary: Path) -> bool:
    """True for a Blender application, False for a `bpy`-carrying Python."""
    return "blender" in binary.stem.lower()


# ── Source resolution ─────────────────────────────────────────────────────────


def read_json(path: Path):
    """
    Read a JSON artifact.

    `paths.py` writes UTF-8, but summaries produced before that was made explicit
    carry the writer's locale encoding (GBK on a Chinese Windows box), so fall
    back rather than making the user regenerate a run.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        print(f"    note: {path.name} is not UTF-8; falling back to the locale encoding")
        return json.loads(path.read_text())


def sources_from_args(args) -> list[tuple[str, Optional[str]]]:
    """Return `[(path, asset_name), ...]` from `--src` or `--summary`."""
    if args.src:
        return [(str(Path(args.src).resolve()), args.name)]

    summary = read_json(Path(args.summary))
    out = []
    for entry in summary:
        if getattr(args, "kind", "mesh") == "motion":
            path = (
                entry.get("retargeted_fbx_path")
                or entry.get("anim_only_fbx_path")
                or entry.get("glb_path")
            )
        else:
            path = entry.get("glb_path")
        if path:
            out.append((str(Path(path).resolve()), entry.get("task_id")))
    if not out:
        raise SystemExit(f"no artifacts listed in {args.summary}")
    return out


def validate_source(path: str) -> dict:
    """
    Check the artifact before spending an engine launch on it.

    Catches the cheap failures: a missing file, a "GLB" that is actually an error
    page the download step never noticed, and a `.ply` that turns out to be the
    Gaussian-splat half of a world and carries no geometry at all.
    """
    p = Path(path)
    info: dict = {"path": str(p), "exists": p.is_file()}
    if not info["exists"]:
        info["error"] = "file does not exist"
        return info
    info["bytes"] = p.stat().st_size
    if p.suffix.lower() in (".glb", ".gltf"):
        info.update(glb_summary(p.read_bytes()))
    elif p.suffix.lower() == ".fbx":
        # FBX is binary; structural validity is proven by the engine importer,
        # not by a host-side parse. A Kaydara header is enough to refuse an
        # empty placeholder before paying for an editor launch.
        header = p.read_bytes()[:24]
        info["format"] = "fbx"
        info["looks_like_fbx"] = header.startswith(b"Kaydara FBX Binary") or (
            b"FBX" in header
        )
        if info["bytes"] < 64 or not info["looks_like_fbx"]:
            info["error"] = "file does not look like an FBX"
    elif p.suffix.lower() == ".ply":
        if ply_utils is None:
            info["warning"] = "ply_utils unavailable; skipping PLY inspect"
        else:
            try:
                info.update(ply_utils.describe(p))
            except (ply_utils.PlyError, OSError) as e:
                info["error"] = str(e)
    return info


# ── Command construction ──────────────────────────────────────────────────────


def _ue_importer(args) -> Path:
    return UE_MOTION_IMPORTER if getattr(args, "kind", "mesh") == "motion" else UE_IMPORTER


def _blender_importer(args) -> Path:
    return (
        BLENDER_MOTION_IMPORTER
        if getattr(args, "kind", "mesh") == "motion"
        else BLENDER_IMPORTER
    )


def ue_command(editor: Path, uproject: Path, src: str, args,
               asset_name: Optional[str], report: Path,
               source_tris: Optional[int] = None) -> tuple[list[str], dict]:
    """
    UnrealEditor-Cmd invocation that runs `import_mesh.py` or
    `import_motion.py` in the project.

    Parameters travel in a JSON job file named by `$AAAGF_IMPORT_JOB` rather than
    on the command line: `-script="file.py --a b"` has to survive both the shell
    and UE's own argument parser, and paths lose their quoting on the way.

    Returns:
        (command, extra environment)
    """
    importer = _ue_importer(args)
    if getattr(args, "kind", "mesh") == "motion":
        job = {
            "src": src,
            "dest": getattr(args, "ue_motion_dest", None) or "/Game/Generated/Motion",
            "name": asset_name,
            "existing_skeleton": getattr(args, "ue_skeleton", None),
            "no_mesh": bool(getattr(args, "ue_anim_only", False)),
            "report": str(report),
        }
    else:
        job = {
            "src": src,
            "dest": args.ue_dest,
            "name": asset_name,
            "usage": args.usage,
            "target_tris": args.target_tris,
            "pivot": args.pivot,
            "normalize_scale": args.normalize_scale,
            "report": str(report),
            # Read from the file here so the engine side can flag a mismatch — under
            # Nanite, UE reports the fallback mesh, not the source density.
            "source_tris": source_tris,
        }
    job_path = report.with_name(report.stem + "_job.json")
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

    env = {"AAAGF_IMPORT_JOB": str(job_path)}
    if args.ue_mode == "editor":
        # Full editor: Slate exists, so the post-import Content Browser sync that
        # AssetTools performs cannot assert. Costs a real editor window and a
        # slower start, and the script has to close it when it is done.
        command = [
            str(_prefer_gui_binary(editor)), str(uproject),
            f"-ExecutePythonScript={importer}",
            "-unattended", "-nopause", "-nosplash", "-stdout", "-utf8output",
        ]
        env["AAAGF_UE_QUIT_WHEN_DONE"] = "1"
    else:
        command = [
            str(editor), str(uproject),
            "-run=pythonscript", f"-script={importer}",
            "-unattended", "-nopause", "-nosplash", "-stdout", "-utf8output",
        ]
    command += list(args.ue_extra or [])
    if args.ue_route:
        env["AAAGF_UE_IMPORT_ROUTE"] = args.ue_route
    return command, env


def _prefer_gui_binary(path: Path) -> Path:
    """`UnrealEditor-Cmd.exe` → `UnrealEditor.exe` when that one exists."""
    if not path.stem.endswith("-Cmd"):
        return path
    gui = path.with_name(path.stem[: -len("-Cmd")] + path.suffix)
    return gui if gui.exists() else path


def unity_command(unity: Path, project: Path, src: str, args,
                  asset_name: Optional[str], report: Path) -> list[str]:
    """Unity batch-mode invocation of `ImportGeneratedMesh.RunFromCLI`."""
    cmd = [
        str(unity), "-batchmode", "-quit", "-nographics",
        "-projectPath", str(project),
        "-executeMethod", "ImportGeneratedMesh.RunFromCLI",
        "-logFile", str(report.with_suffix(".unity.log")),
        "--src", src,
        "--dest", args.unity_dest,
        "--usage", args.usage,
        "--report", str(report),
    ]
    if asset_name:
        cmd += ["--name", asset_name]
    if args.target_tris:
        cmd += ["--target-tris", str(args.target_tris)]
    if args.pivot:
        cmd += ["--pivot", args.pivot]
    if args.normalize_scale:
        cmd += ["--normalize-scale"]
    return cmd


def blender_command(binary: Path, src: str, args, asset_name: Optional[str],
                    report: Path, source_tris: Optional[int] = None
                    ) -> tuple[list[str], dict]:
    """
    Blender invocation that runs `import_mesh.py` or `import_motion.py`
    with no project and no window.

    Parameters travel in the same JSON job file the UE5 route uses: Blender puts
    everything after a bare `--` into `sys.argv` untouched, but one job shape for
    every engine is worth more than saving a file.

    Returns:
        (command, extra environment)
    """
    importer = _blender_importer(args)
    if getattr(args, "kind", "mesh") == "motion":
        job = {
            "src": src,
            "dest": args.blender_dest or str(report.parent / "blender_library"),
            "name": asset_name,
            "export": args.blender_export,
            "preview": args.blender_preview,
            "report": str(report),
        }
    else:
        job = {
            "src": src,
            "dest": args.blender_dest or str(report.parent / "blender_library"),
            "name": asset_name,
            "usage": args.usage,
            "target_tris": args.target_tris,
            "source_tris": source_tris,
            "pivot": args.pivot,
            "normalize_scale": args.normalize_scale,
            "export": args.blender_export,
            "preview": args.blender_preview,
            "report": str(report),
        }
    job_path = report.with_name(report.stem + "_job.json")
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

    if is_blender_app(binary):
        command = [str(binary), "--background", "--factory-startup",
                   "--python", str(importer)]
    else:
        command = [str(binary), str(importer)]
    return command, {"AAAGF_IMPORT_JOB": str(job_path),
                     "AAAGF_BLENDER_EXIT_ON_DONE": "1"}


def _quote(value: str) -> str:
    return f'"{value}"' if " " in value else value


def install_unity_editor_script(project: Path) -> Path:
    """
    Copy the importer into `<project>/Assets/Editor/`.

    Unity only compiles editor code that sits in a folder named `Editor`, so the
    file cannot simply be referenced from this repo.
    """
    dest_dir = project / "Assets" / "Editor"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / UNITY_IMPORTER.name
    shutil.copy2(UNITY_IMPORTER, dest)
    return dest


# ── Run ───────────────────────────────────────────────────────────────────────


def run_engine(cmd: list[str], report_path: Path, label: str,
               timeout: int, dry_run: bool,
               extra_env: Optional[dict] = None,
               cwd: Optional[Path] = None) -> dict:
    """Run one engine invocation and return the report it wrote."""
    printable = " ".join(_quote(c) for c in cmd)
    print(f"\n[{label}] {printable}")
    for key, value in (extra_env or {}).items():
        print(f"[{label}] {key}={value}")
    if dry_run:
        return {"ok": None, "dry_run": True, "command": printable}

    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        report_path.unlink()

    env = {**os.environ, **(extra_env or {})}
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(cwd) if cwd is not None else None,
                          env=env, errors="replace")
    tail = (proc.stdout or "")[-2000:]
    if proc.returncode != 0:
        print(f"[{label}] exit code {proc.returncode}")
        print(tail)

    if report_path.is_file():
        report = read_json(report_path)
    else:
        report = {"ok": False,
                  "error": f"{label} wrote no report (exit {proc.returncode}); "
                           f"see the engine log",
                  "stdout_tail": tail}
    report["exit_code"] = proc.returncode
    return report


def summarize(label: str, report: dict) -> None:
    if report.get("dry_run"):
        print(f"[{label}] dry run — command printed, engine not launched")
        return
    if report.get("ok"):
        asset = (report.get("assetPath") or report.get("asset_path")
                 or report.get("object"))
        # Only Unity makes a prefab; naming it for the others reads as a failure.
        prefab = report.get("prefabPath")
        print(f"[{label}] OK  asset={asset}  "
              f"{f'prefab={prefab}  ' if prefab else ''}"
              f"tris={report.get('triangles') or report.get('tris')}")
        for kind, path in (report.get("exports") or {}).items():
            print(f"[{label}]   {kind}: {path}")
        if report.get("preview"):
            print(f"[{label}]   preview: {report['preview']}")
    else:
        print(f"[{label}] FAILED  {report.get('error')}")
    for w in report.get("warnings", []):
        print(f"[{label}]   warning: {w}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--src", help="One generated .glb / .fbx")
    src.add_argument("--summary", help="A <kind>_results_summary.json from run.py")

    ap.add_argument("--engine", default="both",
                    choices=["ue5", "unity", "blender", "both", "all"],
                    help="'both' is UE5 + Unity; 'all' adds Blender")
    ap.add_argument(
        "--kind",
        default="mesh",
        choices=list(KINDS),
        help=(
            "'mesh' (default) runs the static-prop importers; 'motion' runs "
            "import_motion.py and expects a retargeted .fbx"
        ),
    )
    ap.add_argument("--name", default=None, help="Asset name (single --src only)")
    ap.add_argument("--usage", default="asset", choices=USAGES,
                    help="Import tier; 'asset' imports verbatim (part B4); "
                         "'motion' is implied by --kind motion")
    ap.add_argument(
        "--ue-skeleton",
        default=None,
        help="For --kind motion: import animation onto this existing Skeleton",
    )
    ap.add_argument(
        "--ue-anim-only",
        action="store_true",
        help="For --kind motion: do not import a SkeletalMesh (needs --ue-skeleton)",
    )
    ap.add_argument(
        "--ue-motion-dest",
        default="/Game/Generated/Motion",
        help="UE package path for motion imports",
    )
    ap.add_argument("--target-tris", type=int, default=None,
                    help="Advisory triangle budget for mesh particles")
    ap.add_argument("--pivot", default=None,
                    choices=["keep", "center", "bottom", "top"])
    ap.add_argument("--normalize-scale", action="store_true")

    ap.add_argument("--ue-editor", default=None, help="UnrealEditor-Cmd path")
    ap.add_argument("--uproject", default=os.environ.get("AAAGF_UPROJECT"))
    ap.add_argument("--ue-dest", default="/Game/Generated/Meshes")
    ap.add_argument("--ue-mode", default=os.environ.get("AAAGF_UE_MODE", "editor"),
                    choices=["editor", "commandlet"],
                    help="'editor' launches the full editor (Slate exists, so the "
                         "post-import Content Browser sync cannot assert); "
                         "'commandlet' is faster but crashes on some 5.x builds")
    ap.add_argument("--ue-route", default=os.environ.get("AAAGF_UE_IMPORT_ROUTE"),
                    choices=["automated", "interchange", "task"],
                    help="Force one import API instead of trying them in order")
    ap.add_argument("--ue-extra", action="append", default=None, metavar="ARG",
                    help="Extra UE command-line argument, repeatable. Because the "
                         "value itself starts with a dash, attach it with '=': "
                         "--ue-extra=-EnablePlugins=PythonScriptPlugin  (that one "
                         "imports into a project without editing its .uproject)")
    ap.add_argument("--unity", default=None, help="Unity editor binary path")
    ap.add_argument("--unity-project", default=os.environ.get("AAAGF_UNITY_PROJECT"))
    ap.add_argument("--unity-dest", default="Assets/Generated/Meshes")
    ap.add_argument("--no-install-editor-script", action="store_true",
                    help="Do not copy ImportGeneratedMesh.cs into the Unity project")

    ap.add_argument("--blender", default=None,
                    help="blender(.exe), or a python that can import bpy")
    ap.add_argument("--blender-dest", default=None,
                    help="Library directory for the conditioned copies "
                         "(default: blender_library/ next to the report)")
    ap.add_argument("--blender-export", nargs="*", default=["glb"],
                    choices=["glb", "fbx", "blend"],
                    help="Formats Blender writes back out")
    ap.add_argument("--blender-preview", action="store_true",
                    help="Also render a poster frame of what came in")

    ap.add_argument("--report-dir", default=None,
                    help="Where engine reports land (default: next to the source)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate the artifact and print the commands only")
    args = ap.parse_args()

    engines = ENGINE_SETS.get(args.engine, [args.engine])
    sources = sources_from_args(args)

    failures = 0
    for path, asset_name in sources:
        info = validate_source(path)
        print(f"\n=== {path}")
        print(f"    {json.dumps(info, ensure_ascii=False)}")
        if not info.get("exists"):
            failures += 1
            continue
        if info.get("triangles") == 0:
            print("    warning: the GLB parses but contains no triangles")
        if info.get("error"):
            print(f"    error: {info['error']}")
            failures += 1
            continue

        # Unity is launched with the generated project as cwd so project-
        # relative Assets paths behave like the Editor. Keep host reports
        # absolute so that cwd does not relocate them into the project.
        report_dir = (
            Path(args.report_dir).expanduser().resolve(strict=False)
            if args.report_dir
            else Path(path).parent.resolve(strict=False)
        )
        stem = asset_name or Path(path).stem

        for engine in engines:
            if args.kind == "motion" and engine == "unity":
                print("[unity] --kind motion is not wired yet; use blender or ue5")
                failures += 1
                continue
            extra_env: dict = {}
            if engine == "ue5":
                editor = find_unreal_editor(args.ue_editor)
                if not editor or not editor.exists():
                    print("[ue5] no UnrealEditor-Cmd found — pass --ue-editor or set "
                          "AAAGF_UE_EDITOR")
                    failures += 1
                    continue
                if not args.uproject:
                    print("[ue5] no project — pass --uproject or set AAAGF_UPROJECT")
                    failures += 1
                    continue
                report_path = report_dir / f"{stem}_ue5_import.json"
                cmd, extra_env = ue_command(editor, Path(args.uproject), path, args,
                                            asset_name, report_path,
                                            source_tris=info.get("triangles"))
            elif engine == "blender":
                binary = find_blender(args.blender)
                if not binary or not binary.exists():
                    print("[blender] no Blender found — pass --blender, set "
                          "AAAGF_BLENDER, or `pip install bpy` into this "
                          "environment")
                    failures += 1
                    continue
                report_path = report_dir / f"{stem}_blender_import.json"
                cmd, extra_env = blender_command(binary, path, args, asset_name,
                                                 report_path,
                                                 source_tris=info.get("triangles"))
            else:
                unity = find_unity(args.unity)
                if not unity or not unity.exists():
                    print("[unity] no Unity editor found — pass --unity or set AAAGF_UNITY")
                    failures += 1
                    continue
                if not args.unity_project:
                    print("[unity] no project — pass --unity-project or set "
                          "AAAGF_UNITY_PROJECT")
                    failures += 1
                    continue
                project = Path(args.unity_project).expanduser().resolve(strict=False)
                if not args.no_install_editor_script and not args.dry_run:
                    installed = install_unity_editor_script(project)
                    print(f"[unity] editor script → {installed}")
                report_path = report_dir / f"{stem}_unity_import.json"
                cmd = unity_command(unity, project, path, args, asset_name, report_path)

            report = run_engine(
                cmd,
                report_path,
                engine,
                args.timeout,
                args.dry_run,
                extra_env=extra_env,
                cwd=project if engine == "unity" else None,
            )
            summarize(engine, report)
            if report.get("ok") is False:
                failures += 1

    print(f"\n{'─' * 60}")
    print("FAILED" if failures else "OK", f"({failures} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())