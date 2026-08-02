"""
operators/gen_3d_object/operator.py

Gen3DObjectOperator — accepts a loaded model and processes an input dict into a
3D output (GLB file on disk).

The operator is intentionally model-agnostic: you inject any object that
implements the same interface as Trellis2Model.  New model wrappers can be
swapped in without touching this file.

Output layout — two modes, chosen by whether `output_dir` is given:

  * **per-game (default, `output_dir=None`)** — resolved by
    `pipeline.common.paths`, so artifacts are grouped by generated game project::

        test_data/outputs/<game_id>/<run_id>/assets/3d_object/<task_id>/
            ├── model.glb
            └── meta.json

  * **flat (legacy, `output_dir="..."`)** — writes `<output_dir>/<task_id>.glb`,
    byte-for-byte the historical behaviour. Existing callers are unaffected.

Usage:
    from models.gen_3d_object.trellis_2_model import Trellis2Model
    from operators.gen_3d_object.operator import Gen3DObjectOperator

    model = Trellis2Model(model_path="...")

    # per-game layout
    op = Gen3DObjectOperator(model=model, run_id="20260731_1032")

    # legacy flat layout (unchanged)
    op = Gen3DObjectOperator(model=model, output_dir="outputs/3d_object")

    result = op.run({
        "game_id": "gameA_cyberpunk_shooter",   # optional, inferred when omitted
        "task_id": "sword_001",
        "image_path": "path/to/image.png",      # or "image": PIL.Image
        "seed": 42,
    })
    print(result["glb_path"])
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from PIL import Image

#: Registered task kind for this operator (see pipeline/common/paths.py).
TASK_KIND = "3d_object"

#: Artifact filename used by the per-game layout.
GLB_FILENAME = "model.glb"


class Gen3DObjectOperator:
    """
    Operator for 3D object generation.

    Args:
        model: A loaded model with an `infer_and_save(image, output_path, ...)` method.
               Currently supports Trellis2Model; any model with the same interface works.
        output_dir (str, optional): **Legacy flat mode.** When given, every GLB is
               written as `<output_dir>/<task_id>.glb`, exactly as before. When
               omitted (default), the per-game layout under
               `test_data/outputs/<game_id>/<run_id>/assets/3d_object/<task_id>/`
               is used instead.
        run_id (str): Groups all artifacts of one generation run. Per-game mode only.
        default_game_id (str, optional): Fallback game project for tasks that carry
               no `game_id` and whose input paths reveal none. Per-game mode only.
    """

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
        # Legacy flat mode is active only when an explicit output_dir is supplied.
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------

    def _load_image(self, inp: dict) -> Image.Image:
        """Return a PIL image from an input dict that has 'image_path' or 'image'."""
        if "image" in inp and isinstance(inp["image"], Image.Image):
            return inp["image"]
        if "image_path" in inp:
            p = Path(inp["image_path"])
            if not p.is_absolute() and not p.exists():
                # resolve relative to repo root (codes_official/)
                repo_root = Path(__file__).resolve().parents[2]
                p = repo_root / inp["image_path"]
            return Image.open(str(p)).convert("RGBA")
        raise ValueError("Input must contain 'image_path' (str) or 'image' (PIL.Image).")

    # --------------------------------------------------------------------------

    def _resolve_out_path(self, inp: dict, task_id: str) -> tuple[str, Path, Path]:
        """
        Return ``(game_id, task_dir, glb_path)`` for either output mode.

        Legacy flat mode keeps the historical `<output_dir>/<task_id>.glb`.
        """
        if self.output_dir is not None:
            game_id = str(inp.get("game_id") or inp.get("game") or "")
            return game_id, self.output_dir, self.output_dir / f"{task_id}.glb"

        from pipeline.common import paths
        game_id = paths.infer_game_id(inp, fallback=self.default_game_id)
        task_dir = paths.task_output_dir(game_id, TASK_KIND, task_id, run_id=self.run_id)
        return game_id, task_dir, task_dir / GLB_FILENAME

    # --------------------------------------------------------------------------

    def run(self, inp: dict) -> dict:
        """
        Generate a 3D object from an image prompt.

        Args:
            inp (dict):
                - image_path (str): path to the reference / concept image
                  OR image (PIL.Image): pre-loaded image
                - game_id (str, optional): game project this task belongs to;
                  inferred from `image_path` when omitted
                - task_id (str, optional): used to name the output file / directory
                - seed (int, optional): random seed (default 42)
                - decimation_target (int, optional)
                - texture_size (int, optional)

        Returns:
            dict:
                - task_id (str)
                - glb_path (str): absolute path to the saved GLB file
                - elapsed_sec (float)
                - game_id (str), task_kind (str), output_dir (str)  ← additive
        """
        task_id = inp.get("task_id", f"task_{int(time.time())}")
        seed = inp.get("seed", 42)
        decimation_target = inp.get("decimation_target", 1_000_000)
        texture_size = inp.get("texture_size", 4096)

        game_id, task_dir, out_path = self._resolve_out_path(inp, task_id)

        image = self._load_image(inp)

        t0 = time.time()
        glb_path = self.model.infer_and_save(
            image,
            output_path=str(out_path),
            seed=seed,
            decimation_target=decimation_target,
            texture_size=texture_size,
        )
        elapsed = time.time() - t0

        result = {
            "task_id": task_id,
            "glb_path": glb_path,
            "elapsed_sec": round(elapsed, 2),
            "game_id": game_id,
            "task_kind": TASK_KIND,
            "output_dir": str(task_dir),
        }

        # meta.json only in per-game mode, so legacy output dirs stay untouched.
        if self.output_dir is None:
            from pipeline.common import paths
            paths.write_task_meta(task_dir, {
                **result,
                "run_id": self.run_id,
                "prompt": inp.get("prompt"),
                "source_image": inp.get("image_path"),
                "seed": seed,
                "decimation_target": decimation_target,
                "texture_size": texture_size,
                "model": type(self.model).__name__,
            })

        return result

    # --------------------------------------------------------------------------

    def run_batch(self, inputs: list[dict]) -> list[dict]:
        """Run a list of input dicts sequentially and return results."""
        return [self.run(inp) for inp in inputs]
