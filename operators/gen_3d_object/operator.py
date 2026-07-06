"""
operators/gen_3d_object/operator.py

Gen3DObjectOperator — accepts a loaded model and processes an input dict into a
3D output (GLB file on disk).

The operator is intentionally model-agnostic: you inject any object that
implements the same interface as Trellis2Model.  New model wrappers can be
swapped in without touching this file.

Usage:
    from models.gen_3d_object.trellis_2_model import Trellis2Model
    from operators.gen_3d_object.operator import Gen3DObjectOperator

    model = Trellis2Model(ckpt_path="...")
    op = Gen3DObjectOperator(model=model, output_dir="outputs/3d_object")

    result = op.run({
        "image_path": "path/to/image.png",  # or "image": PIL.Image
        "task_id": "sword_001",
        "seed": 42,
    })
    print(result["glb_path"])
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from PIL import Image


class Gen3DObjectOperator:
    """
    Operator for 3D object generation.

    Args:
        model: A loaded model with an `infer_and_save(image, output_path, ...)` method.
               Currently supports Trellis2Model; any model with the same interface works.
        output_dir (str): Directory to write generated GLB files into.
    """

    def __init__(self, model: Any, output_dir: str = "outputs/3d_object"):
        self.model = model
        self.output_dir = Path(output_dir)
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

    def run(self, inp: dict) -> dict:
        """
        Generate a 3D object from an image prompt.

        Args:
            inp (dict):
                - image_path (str): path to the reference / concept image
                  OR image (PIL.Image): pre-loaded image
                - task_id (str, optional): used to name the output file
                - seed (int, optional): random seed (default 42)
                - decimation_target (int, optional)
                - texture_size (int, optional)

        Returns:
            dict:
                - task_id (str)
                - glb_path (str): absolute path to the saved GLB file
                - elapsed_sec (float)
        """
        task_id = inp.get("task_id", f"task_{int(time.time())}")
        seed = inp.get("seed", 42)
        decimation_target = inp.get("decimation_target", 1_000_000)
        texture_size = inp.get("texture_size", 4096)
        out_path = self.output_dir / f"{task_id}.glb"

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

        return {
            "task_id": task_id,
            "glb_path": glb_path,
            "elapsed_sec": round(elapsed, 2),
        }

    # --------------------------------------------------------------------------

    def run_batch(self, inputs: list[dict]) -> list[dict]:
        """Run a list of input dicts sequentially and return results."""
        return [self.run(inp) for inp in inputs]
