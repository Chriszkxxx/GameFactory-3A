"""AAAGameForge operator for Puppeteer-targeted skeleton motion retargeting."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from .funcs import load_and_validate_mapping


TASK_KIND = "retarget"

RETARGETED_FILENAME = "retargeted.fbx"
ANIMATION_FILENAME = "animation.fbx"
MAPPING_FILENAME = "mapping.json"
INFO_FILENAME = "retarget_info.json"


class RetargetOperator:
    """Turn one motion + Puppeteer target task into retarget artifacts."""

    def __init__(
        self,
        model: Any,
        output_dir: Optional[str] = None,
        run_id: str = "default",
        default_game_id: Optional[str] = None,
    ):
        self.model = model
        self.run_id = run_id
        self.default_game_id = default_game_id
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
            raise ValueError(f"Retarget task requires {key!r}.")
        from pipeline.common import paths

        path = paths.resolve_input_path(value)
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"{key} is missing or empty: {path}")
        return path

    def run(self, inp: dict) -> dict:
        """Execute one retarget task."""
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

        t0 = time.time()
        artifacts = self.model.infer_and_save(
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
                    "model": type(self.model).__name__,
                },
            )
        return result

    def run_batch(self, inputs: list[dict]) -> list[dict]:
        """Run tasks sequentially with the already-loaded model."""
        return [self.run(inp) for inp in inputs]

    def eval(self, result: dict, task: dict) -> dict:
        """Evaluate existing artifacts only."""
        from .metrics import evaluate

        return evaluate(result, task)
