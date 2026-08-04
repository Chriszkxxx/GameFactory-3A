"""Thin wrapper around the Blender/Puppeteer world-delta retarget backend."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


_RETARGET_MODULE = (
    "models.retarget.puppeteer_retarget_utils.world_delta"
)
_MAPPING_MODULE = (
    "models.retarget.puppeteer_retarget_utils.mapping_auto"
)


class PuppeteerRetargetModel:
    """Retarget BVH/FBX animation onto a Puppeteer ``GLB + rig.txt`` target.

    ``model_path`` is the Python executable that can import ``bpy``.  The
    production entry point is :meth:`infer_and_save`; :meth:`infer` provides the
    memory-returning interface required by the AAAGameForge model contract.
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        verbose: bool = False,
    ):
        self.model_path = str(model_path)
        self.device = str(device)
        self.verbose = bool(verbose)
        self._runtime_checked = False

    def infer(
        self,
        source_motion: bytes,
        source_ext: str,
        target_glb: bytes,
        target_rig: str,
        mapping: dict[str, Any] | None = None,
        *,
        fps: int = 30,
        global_scale: float = 1.0,
        root_scale: float | None = None,
        max_delta_deg: float = 0.0,
        bake_root_to_bone: bool = False,
        export_anim_only: bool = True,
        action_name: str | None = None,
    ) -> dict[str, Any]:
        """Return retarget artifacts in memory.

        This path is intended for small inputs and contract-level callers.  For
        normal assets use :meth:`infer_and_save` to avoid reading FBX files back
        through memory.
        """
        ext = self._normalise_source_ext(source_ext)
        with tempfile.TemporaryDirectory(prefix="aaagf_retarget_") as tmp:
            root = Path(tmp)
            source_path = root / f"source{ext}"
            glb_path = root / "target.glb"
            rig_path = root / "target_rig.txt"
            mapping_in = root / "mapping_input.json"
            mapping_out = root / "mapping.json"
            output_path = root / "retargeted.fbx"
            anim_path = root / "animation.fbx"
            info_path = root / "retarget_info.json"

            source_path.write_bytes(source_motion)
            glb_path.write_bytes(target_glb)
            rig_path.write_text(target_rig, encoding="utf-8")
            mapping_path: str | None = None
            if mapping is not None:
                mapping_in.write_text(
                    json.dumps(mapping, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                mapping_path = str(mapping_in)

            self.infer_and_save(
                source_motion_path=str(source_path),
                target_glb_path=str(glb_path),
                target_rig_path=str(rig_path),
                output_path=str(output_path),
                anim_only_output_path=str(anim_path),
                mapping_path=mapping_path,
                mapping_output_path=str(mapping_out),
                info_output_path=str(info_path),
                fps=fps,
                global_scale=global_scale,
                root_scale=root_scale,
                max_delta_deg=max_delta_deg,
                bake_root_to_bone=bake_root_to_bone,
                export_anim_only=export_anim_only,
                action_name=action_name,
            )
            return {
                "retargeted_fbx": output_path.read_bytes(),
                "anim_only_fbx": (
                    anim_path.read_bytes() if export_anim_only else None
                ),
                "mapping": json.loads(
                    mapping_out.read_text(encoding="utf-8-sig")
                ),
                "retarget_info": json.loads(
                    info_path.read_text(encoding="utf-8-sig")
                ),
            }

    def infer_and_save(
        self,
        *,
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
    ) -> dict[str, str | None]:
        """Write retarget artifacts to paths supplied by the caller."""
        self._ensure_runtime()
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

        self._validate_inputs(source, target_glb, target_rig)
        for path in (output, mapping_output, info_output, anim_output):
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)

        if mapping_path:
            mapping_source = Path(mapping_path).resolve()
            self._validate_mapping_file(mapping_source)
            if mapping_source != mapping_output:
                shutil.copyfile(mapping_source, mapping_output)
        else:
            self._run_module(
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
            )
            self._validate_mapping_file(mapping_output)
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

        self._run_module(
            _RETARGET_MODULE,
            [
                *common_args,
                "--output",
                str(output),
                "--info-output",
                str(info_output),
            ],
            expected=[output, info_output],
        )

        if export_anim_only:
            if anim_output is None:
                raise ValueError(
                    "anim_only_output_path is required when export_anim_only=True"
                )
            if mapping_output.read_bytes() != mapping_snapshot:
                mapping_output.write_bytes(mapping_snapshot)
            self._run_module(
                _RETARGET_MODULE,
                [
                    *common_args,
                    "--output",
                    str(anim_output),
                    "--anim-only",
                ],
                expected=[anim_output],
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

    def _ensure_runtime(self) -> None:
        if self._runtime_checked:
            return
        executable = Path(self.model_path)
        if not executable.exists():
            raise RuntimeError(
                "Retarget bpy Python executable does not exist: "
                f"{self.model_path}. Set AAAGF_RETARGET_BPY_PYTHON or "
                "pass --bpy-python."
            )
        proc = subprocess.run(
            [
                str(executable),
                "-c",
                "import bpy, mathutils, numpy, trimesh; print(bpy.app.version_string)",
            ],
            capture_output=True,
            text=True,
            env=self._subprocess_env(),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(
                f"{self.model_path} cannot import the retarget runtime "
                "(bpy, mathutils, numpy, trimesh). Create the Python 3.11 "
                f"retarget environment first. Detail: {detail[-1200:]}"
            )
        self._runtime_checked = True

    def _run_module(
        self,
        module: str,
        args: list[str],
        *,
        expected: list[Path],
    ) -> None:
        started = time.time()
        command = [self.model_path, "-m", module, *args]
        proc = subprocess.run(
            command,
            cwd=str(self._repo_root()),
            env=self._subprocess_env(),
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
            if self.verbose and proc.stdout:
                print(proc.stdout, end="")
            return
        # bpy can occasionally fault during interpreter shutdown after safely
        # flushing an FBX. Accept that case only when every expected artifact is
        # fresh and non-empty.
        if proc.returncode != 0 and valid:
            if self.verbose:
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

    def _subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        root = str(self._repo_root())
        env["PYTHONPATH"] = os.pathsep.join(
            item for item in (root, env.get("PYTHONPATH", "")) if item
        )
        if self.device.lower() == "cpu":
            env["CUDA_VISIBLE_DEVICES"] = ""
        if os.name != "nt":
            conda_lib = Path(self.model_path).resolve().parent.parent / "lib"
            if conda_lib.is_dir():
                env["LD_LIBRARY_PATH"] = os.pathsep.join(
                    item
                    for item in (
                        str(conda_lib),
                        env.get("LD_LIBRARY_PATH", ""),
                    )
                    if item
                )
        env.pop("PYOPENGL_PLATFORM", None)
        return env

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def _normalise_source_ext(value: str) -> str:
        ext = value.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext not in {".bvh", ".fbx"}:
            raise ValueError(
                f"source_ext must be '.bvh' or '.fbx', got {value!r}"
            )
        return ext

    @classmethod
    def _validate_inputs(
        cls,
        source: Path,
        target_glb: Path,
        target_rig: Path,
    ) -> None:
        cls._normalise_source_ext(source.suffix)
        for label, path in (
            ("source motion", source),
            ("target GLB", target_glb),
            ("target rig", target_rig),
        ):
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(f"{label} is missing or empty: {path}")
        if target_glb.suffix.lower() != ".glb":
            raise ValueError(f"target_glb_path must end in .glb: {target_glb}")

    @staticmethod
    def _validate_mapping_file(path: Path) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Retarget mapping is missing or empty: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid retarget mapping JSON: {path}: {exc}") from exc
        bone_map = data.get("bone_map")
        if not isinstance(bone_map, dict) or not bone_map:
            raise ValueError(f"Retarget mapping has no non-empty 'bone_map': {path}")
        if not all(
            isinstance(source, str)
            and source
            and isinstance(target, str)
            and target
            for source, target in bone_map.items()
        ):
            raise ValueError(
                f"Retarget mapping bone_map must contain string-to-string entries: {path}"
            )
