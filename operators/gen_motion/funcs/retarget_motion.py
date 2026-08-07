"""File-oriented Puppeteer motion retargeting for ``gen_motion``.

This module is a deterministic Blender function, not a learned model wrapper.
The caller owns every input and output path; this function only validates the
runtime and invokes the Blender backend.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from .puppeteer_retarget.validate_mapping import load_and_validate_mapping


_RETARGET_MODULE = (
    "operators.gen_motion.funcs.puppeteer_retarget.world_delta"
)
_MAPPING_MODULE = (
    "operators.gen_motion.funcs.puppeteer_retarget.mapping_auto"
)


def retarget_motion(
    *,
    bpy_python: str,
    source_motion_path: str,
    target_glb_path: str,
    target_rig_path: str,
    output_path: str,
    anim_only_output_path: str | None,
    mapping_path: str | None,
    mapping_output_path: str,
    info_output_path: str,
    fps: int = 30,
    global_scale: float = 1.0,
    root_scale: float | None = None,
    max_delta_deg: float = 0.0,
    bake_root_to_bone: bool = False,
    export_anim_only: bool = True,
    action_name: str | None = None,
    device: str = "cpu",
    verbose: bool = False,
) -> dict[str, str | None]:
    """Retarget one BVH/FBX clip and write artifacts to caller-owned paths."""
    ensure_retarget_runtime(bpy_python, device=device)
    source = Path(source_motion_path).resolve()
    target_glb = Path(target_glb_path).resolve()
    target_rig = Path(target_rig_path).resolve()
    output = Path(output_path).resolve()
    mapping_output = Path(mapping_output_path).resolve()
    info_output = Path(info_output_path).resolve()
    anim_output = (
        Path(anim_only_output_path).resolve()
        if anim_only_output_path is not None
        else None
    )

    _validate_inputs(source, target_glb, target_rig)
    for path in (output, mapping_output, info_output, anim_output):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    if mapping_path:
        mapping_source = Path(mapping_path).resolve()
        load_and_validate_mapping(mapping_source)
        if mapping_source != mapping_output:
            shutil.copyfile(mapping_source, mapping_output)
    else:
        _run_module(
            bpy_python,
            _MAPPING_MODULE,
            [
                "--glb",
                str(target_glb),
                "--rig",
                str(target_rig),
                "--source-anim",
                str(source),
                "--global-scale",
                str(float(global_scale)),
                "--output",
                str(mapping_output),
            ],
            expected=[mapping_output],
            device=device,
            verbose=verbose,
        )
        load_and_validate_mapping(mapping_output)
    mapping_snapshot = mapping_output.read_bytes()

    common_args = [
        "--glb",
        str(target_glb),
        "--rig",
        str(target_rig),
        "--source-anim",
        str(source),
        "--mapping",
        str(mapping_output),
        "--fps",
        str(int(fps)),
        "--global-scale",
        str(float(global_scale)),
        "--max-delta-deg",
        str(float(max_delta_deg)),
    ]
    if root_scale is not None:
        common_args += ["--root-scale", str(float(root_scale))]
    if bake_root_to_bone:
        common_args.append("--bake-root-to-bone")
    if action_name:
        common_args += ["--action-name", str(action_name)]

    _run_module(
        bpy_python,
        _RETARGET_MODULE,
        [
            *common_args,
            "--output",
            str(output),
            "--info-output",
            str(info_output),
        ],
        expected=[output, info_output],
        device=device,
        verbose=verbose,
    )

    if export_anim_only:
        if anim_output is None:
            raise ValueError(
                "anim_only_output_path is required when export_anim_only=True"
            )
        if mapping_output.read_bytes() != mapping_snapshot:
            mapping_output.write_bytes(mapping_snapshot)
        _run_module(
            bpy_python,
            _RETARGET_MODULE,
            [
                *common_args,
                "--output",
                str(anim_output),
                "--anim-only",
            ],
            expected=[anim_output],
            device=device,
            verbose=verbose,
        )
    if mapping_output.read_bytes() != mapping_snapshot:
        mapping_output.write_bytes(mapping_snapshot)

    return {
        "retargeted_fbx_path": str(output),
        "anim_only_fbx_path": (
            str(anim_output) if export_anim_only and anim_output else None
        ),
        "mapping_path": str(mapping_output),
        "retarget_info_path": str(info_output),
    }


@lru_cache(maxsize=8)
def ensure_retarget_runtime(
    bpy_python: str,
    *,
    device: str = "cpu",
) -> str:
    """Validate a Python executable containing bpy and return its path."""
    executable = Path(bpy_python)
    if not executable.is_file():
        raise RuntimeError(
            "Retarget bpy Python executable does not exist: "
            f"{bpy_python}. Set AAAGF_RETARGET_BPY_PYTHON or pass "
            "--bpy-python."
        )
    proc = subprocess.run(
        [
            str(executable),
            "-c",
            "import bpy, mathutils, numpy, trimesh; print(bpy.app.version_string)",
        ],
        capture_output=True,
        text=True,
        env=_subprocess_env(str(executable), device),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(
            f"{bpy_python} cannot import the retarget runtime "
            "(bpy, mathutils, numpy, trimesh). Create the Python 3.11 "
            f"retarget environment first. Detail: {detail[-1200:]}"
        )
    return str(executable.resolve())


def normalise_source_ext(value: str) -> str:
    """Return a validated lower-case ``.bvh`` or ``.fbx`` extension."""
    ext = value.lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext not in {".bvh", ".fbx"}:
        raise ValueError(
            f"source_ext must be '.bvh' or '.fbx', got {value!r}"
        )
    return ext


def _validate_inputs(
    source: Path,
    target_glb: Path,
    target_rig: Path,
) -> None:
    normalise_source_ext(source.suffix)
    for label, path in (
        ("source motion", source),
        ("target GLB", target_glb),
        ("target rig", target_rig),
    ):
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"{label} is missing or empty: {path}")
    if target_glb.suffix.lower() != ".glb":
        raise ValueError(f"target_glb_path must end in .glb: {target_glb}")


def _run_module(
    bpy_python: str,
    module: str,
    args: list[str],
    *,
    expected: list[Path],
    device: str,
    verbose: bool,
) -> None:
    started = time.time()
    command = [bpy_python, "-m", module, *args]
    proc = subprocess.run(
        command,
        cwd=str(_repo_root()),
        env=_subprocess_env(bpy_python, device),
        capture_output=True,
        text=True,
    )
    valid = all(
        path.exists()
        and path.stat().st_size > 0
        and path.stat().st_mtime >= started - 1.0
        for path in expected
    )
    if proc.returncode == 0 and valid:
        if verbose and proc.stdout:
            print(proc.stdout, end="")
        return
    # bpy can fault during interpreter shutdown after flushing a valid FBX.
    if proc.returncode != 0 and valid:
        if verbose:
            print(
                f"[retarget] bpy exited {proc.returncode} after writing "
                "all requested artifacts; accepting the completed output."
            )
        return

    missing = [
        str(path)
        for path in expected
        if not path.exists() or path.stat().st_size == 0
    ]
    stdout = (proc.stdout or "")[-2000:]
    stderr = (proc.stderr or "")[-2000:]
    raise RuntimeError(
        "Retarget bpy subprocess failed.\n"
        f"Command: {subprocess.list2cmdline(command)}\n"
        f"Return code: {proc.returncode}\n"
        f"Missing/empty outputs: {missing}\n"
        f"stdout tail:\n{stdout}\n"
        f"stderr tail:\n{stderr}"
    )


def _subprocess_env(bpy_python: str, device: str) -> dict[str, str]:
    env = os.environ.copy()
    root = str(_repo_root())
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in (root, env.get("PYTHONPATH", "")) if item
    )
    if device.lower() == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    if os.name != "nt":
        conda_lib = Path(bpy_python).resolve().parent.parent / "lib"
        if conda_lib.is_dir():
            env["LD_LIBRARY_PATH"] = os.pathsep.join(
                item
                for item in (str(conda_lib), env.get("LD_LIBRARY_PATH", ""))
                if item
            )
    env.pop("PYOPENGL_PLATFORM", None)
    return env


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


__all__ = [
    "ensure_retarget_runtime",
    "normalise_source_ext",
    "retarget_motion",
]
