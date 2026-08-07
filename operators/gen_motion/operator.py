"""AAAGameForge operator for motion generation and related functions.

The current implementation exposes the deterministic Puppeteer retarget
function. Learned rigging and text-to-motion models will be injected here in
future changes rather than represented as separate task kinds.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


TASK_KIND = "motion"

RETARGETED_FILENAME = "retargeted.fbx"
ANIMATION_FILENAME = "animation.fbx"
MAPPING_FILENAME = "mapping.json"
INFO_FILENAME = "retarget_info.json"


class GenMotionOperator:
    """Turn one motion task into artifacts under the shared motion task kind."""

    def __init__(
        self,
        bpy_python: str | None = None,
        output_dir: Optional[str] = None,
        run_id: str = "default",
        default_game_id: Optional[str] = None,
        *,
        device: str = "cpu",
        verbose: bool = False,
        retarget_fn: Callable[..., dict] | None = None,
    ):
        self.bpy_python = str(bpy_python) if bpy_python else None
        self.run_id = run_id
        self.default_game_id = default_game_id
        self.device = str(device)
        self.verbose = bool(verbose)
        self.retarget_fn = retarget_fn
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_outputs(
        self,
        inp: dict,
        task_id: str,
    ) -> tuple[str, Path, Path, Path, Path, Path]:
        if self.output_dir is not None:
            root = self.output_dir
            return (
                "",
                root,
                root / f"{task_id}.fbx",
                root / f"{task_id}_anim_only.fbx",
                root / f"{task_id}_mapping.json",
                root / f"{task_id}_retarget_info.json",
            )

        from pipeline.common import paths

        game_id = paths.infer_game_id(inp, fallback=self.default_game_id)
        root = paths.task_output_dir(
            game_id,
            TASK_KIND,
            task_id,
            run_id=self.run_id,
        )
        return (
            game_id,
            root,
            root / RETARGETED_FILENAME,
            root / ANIMATION_FILENAME,
            root / MAPPING_FILENAME,
            root / INFO_FILENAME,
        )

    @staticmethod
    def _required_path(inp: dict, key: str) -> Path:
        value = inp.get(key)
        if not value:
            raise ValueError(f"Motion retarget task requires {key!r}.")
        from pipeline.common import paths

        path = paths.resolve_input_path(value)
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"{key} is missing or empty: {path}")
        return path

    def run(self, inp: dict) -> dict:
        """Execute one motion task; currently ``task_type=retarget`` only."""
        task_type = str(inp.get("task_type", "retarget")).lower()
        if task_type != "retarget":
            raise NotImplementedError(
                "GenMotionOperator currently supports only "
                f"task_type='retarget', got {task_type!r}. Puppeteer rigging "
                "and text-to-motion generation are not part of this change."
            )

        task_id = str(inp.get("task_id", f"task_{int(time.time())}"))
        source_motion = self._required_path(inp, "source_motion_path")
        target_glb = self._required_path(inp, "target_glb_path")
        target_rig = self._required_path(inp, "target_rig_path")

        if source_motion.suffix.lower() not in {".bvh", ".fbx"}:
            raise ValueError(
                "source_motion_path must end in .bvh or .fbx: "
                f"{source_motion}"
            )
        if target_glb.suffix.lower() != ".glb":
            raise ValueError(f"target_glb_path must end in .glb: {target_glb}")

        mapping_path: Path | None = None
        mapping_value = inp.get("mapping_path")
        if mapping_value:
            from pipeline.common import paths
            from .funcs.puppeteer_retarget.validate_mapping import (
                load_and_validate_mapping,
            )

            mapping_path = paths.resolve_input_path(mapping_value)
            load_and_validate_mapping(mapping_path)

        seed = int(inp.get("seed", 42))
        fps = int(inp.get("fps", 30))
        if fps <= 0:
            raise ValueError(f"fps must be positive, got {fps}")
        global_scale = float(inp.get("global_scale", 1.0))
        if global_scale <= 0:
            raise ValueError(
                f"global_scale must be positive, got {global_scale}"
            )
        root_scale_value = inp.get("root_scale")
        root_scale = (
            None if root_scale_value is None else float(root_scale_value)
        )
        max_delta_deg = float(inp.get("max_delta_deg", 0.0))
        if max_delta_deg < 0:
            raise ValueError(
                f"max_delta_deg must be non-negative, got {max_delta_deg}"
            )
        bake_root_to_bone = bool(inp.get("bake_root_to_bone", False))
        export_anim_only = bool(inp.get("export_anim_only", True))
        action_name = inp.get("action_name")

        (
            game_id,
            task_dir,
            retargeted_path,
            anim_only_path,
            mapping_output,
            info_output,
        ) = self._resolve_outputs(inp, task_id)

        retarget_fn = self.retarget_fn
        if retarget_fn is None:
            if not self.bpy_python:
                raise RuntimeError(
                    "Motion retargeting requires a bpy Python executable. "
                    "Pass bpy_python to GenMotionOperator or use "
                    "--bpy-python in the gen_motion pipeline."
                )
            from .funcs.retarget_motion import retarget_motion

            retarget_fn = retarget_motion

        t0 = time.time()
        artifacts = retarget_fn(
            bpy_python=self.bpy_python or "",
            source_motion_path=str(source_motion),
            target_glb_path=str(target_glb),
            target_rig_path=str(target_rig),
            output_path=str(retargeted_path),
            anim_only_output_path=str(anim_only_path),
            mapping_path=str(mapping_path) if mapping_path else None,
            mapping_output_path=str(mapping_output),
            info_output_path=str(info_output),
            fps=fps,
            global_scale=global_scale,
            root_scale=root_scale,
            max_delta_deg=max_delta_deg,
            bake_root_to_bone=bake_root_to_bone,
            export_anim_only=export_anim_only,
            action_name=str(action_name) if action_name else None,
            device=self.device,
            verbose=self.verbose,
        )
        elapsed = time.time() - t0

        result = {
            "task_id": task_id,
            "retargeted_fbx_path": artifacts["retargeted_fbx_path"],
            "anim_only_fbx_path": artifacts.get("anim_only_fbx_path"),
            "mapping_path": artifacts["mapping_path"],
            "retarget_info_path": artifacts["retarget_info_path"],
            "elapsed_sec": round(elapsed, 2),
            "game_id": game_id,
            "task_kind": TASK_KIND,
            "output_dir": str(task_dir),
        }

        if self.output_dir is None:
            from pipeline.common import paths

            paths.write_task_meta(
                task_dir,
                {
                    **result,
                    "run_id": self.run_id,
                    "task_type": task_type,
                    "source_motion_path": str(source_motion),
                    "target_glb_path": str(target_glb),
                    "target_rig_path": str(target_rig),
                    "source_mapping_path": (
                        str(mapping_path) if mapping_path else None
                    ),
                    "seed": seed,
                    "fps": fps,
                    "global_scale": global_scale,
                    "root_scale": root_scale,
                    "max_delta_deg": max_delta_deg,
                    "bake_root_to_bone": bake_root_to_bone,
                    "export_anim_only": export_anim_only,
                    "retarget_runtime": self.bpy_python,
                },
            )
        return result

    def run_batch(self, inputs: list[dict]) -> list[dict]:
        """Run tasks sequentially with the configured function dependencies."""
        return [self.run(inp) for inp in inputs]

    def eval(self, result: dict, task: dict) -> dict:
        """Evaluate existing artifacts only."""
        from .metrics import evaluate

        return evaluate(result, task)
