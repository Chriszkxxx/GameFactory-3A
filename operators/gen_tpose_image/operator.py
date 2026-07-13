"""
operators/gen_tpose_image/operator.py

GenTPoseImageOperator — accepts a loaded image-edit model (and an optional
foreground / matting model) and processes an input dict into a T-pose RGBA
image saved as PNG.

The operator is intentionally model-agnostic: you inject any object that
implements the same interface as `QwenEditModel` (`.edit(image, prompt, seed,
steps) -> PIL.Image`), and any tool model that behaves like `RMBGModel` or
`DepthAnythingModel` (`.predict(image) -> np.ndarray`). New model wrappers
can be swapped in without touching this file.

Usage:
    from models.gen_image.qwen_edit import QwenEditModel
    from models.tools.image_matting.rmbg import RMBGModel
    from operators.gen_tpose_image.operator import GenTPoseImageOperator

    gen_model  = QwenEditModel(model_path="Qwen/Qwen-Image-Edit-2511")
    mask_model = RMBGModel(model_path="briaai/RMBG-1.4")
    op = GenTPoseImageOperator(
        gen_model=gen_model,
        mask_model=mask_model,
        output_dir="outputs/tpose",
    )

    result = op.run({
        "image_path": "path/to/character.png",  # or "image": PIL.Image
        "task_id": "luffy_001",
        "description": "Monkey D. Luffy in a red vest and straw hat.",
        "seed": 42,
    })
    print(result["tpose_rgba_path"])
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from PIL import Image


class GenTPoseImageOperator:
    """
    Operator for character T-pose image generation.

    Args:
        gen_model:  A loaded image-edit model with an
                    `.edit(image, prompt, seed, steps) -> PIL.Image` method
                    (currently supports QwenEditModel).
        mask_model: (optional) A loaded foreground / matting model — either
                    `RMBGModel` or `DepthAnythingModel` (or any object with a
                    `.predict(image) -> np.ndarray` method). The extraction
                    branch is selected automatically based on the class name.
        output_dir (str): Directory to write generated PNG files into.
    """

    def __init__(
        self,
        gen_model: Any,
        mask_model: Optional[Any] = None,
        output_dir: str = "outputs/tpose",
    ):
        self.gen_model = gen_model
        self.mask_model = mask_model
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
                # resolve relative to repo root
                repo_root = Path(__file__).resolve().parents[2]
                p = repo_root / inp["image_path"]
            return Image.open(str(p)).convert("RGB")
        raise ValueError("Input must contain 'image_path' (str) or 'image' (PIL.Image).")

    # --------------------------------------------------------------------------

    def run(self, inp: dict) -> dict:
        """
        Generate a T-pose RGBA image from a reference character image.

        Args:
            inp (dict):
                - image_path (str): path to the reference character image
                  OR image (PIL.Image): pre-loaded image
                - task_id (str, optional): used to name the output file
                - description (str, optional): short text description of the character
                - seed (int, optional): random seed (default 42)
                - steps (int, optional): diffusion steps (default 40)
                - target_size (int, optional): output square canvas size (default 1024)
                - save_intermediate (bool, optional): also save the white-bg RGB
                                                     T-pose (default True)

        Returns:
            dict:
                - task_id (str)
                - tpose_rgb_path (str | None): path to the white-bg RGB T-pose PNG
                - tpose_rgba_path (str): path to the transparent-bg T-pose PNG
                - elapsed_sec (float)
        """
        from operators.gen_tpose_image.funcs.gen_tpose_image import gen_tpose_image

        task_id           = inp.get("task_id", f"task_{int(time.time())}")
        description       = inp.get("description", "")
        seed              = inp.get("seed", 42)
        steps             = inp.get("steps", 40)
        target_size       = inp.get("target_size", 1024)
        save_intermediate = inp.get("save_intermediate", True)

        ref_image = self._load_image(inp)

        t0 = time.time()
        result = gen_tpose_image(
            ref_image,
            description=description,
            gen_model=self.gen_model,
            mask_model=self.mask_model,
            seed=seed,
            steps=steps,
            target_size=target_size,
            return_intermediate=True,
        )
        elapsed = time.time() - t0

        tpose_rgb  = result["tpose_rgb"]
        tpose_rgba = result["tpose_rgba"]

        rgba_path = self.output_dir / f"{task_id}_tpose_fg.png"
        tpose_rgba.save(str(rgba_path))

        rgb_path: Optional[Path] = None
        if save_intermediate:
            rgb_path = self.output_dir / f"{task_id}_tpose.png"
            tpose_rgb.save(str(rgb_path))

        return {
            "task_id": task_id,
            "tpose_rgb_path": str(rgb_path) if rgb_path is not None else None,
            "tpose_rgba_path": str(rgba_path),
            "elapsed_sec": round(elapsed, 2),
        }

    # --------------------------------------------------------------------------

    def run_batch(self, inputs: list[dict]) -> list[dict]:
        """Run a list of input dicts sequentially and return results."""
        return [self.run(inp) for inp in inputs]
