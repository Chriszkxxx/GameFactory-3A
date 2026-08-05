"""
RMBGModel — background removal wrapper for BRIA `RMBG-1.4`.

Reference: https://huggingface.co/briaai/RMBG-1.4

Conforms to `BaseToolModel`. Given an RGB PIL image, `infer()` returns a
HxW float32 numpy array in [0, 1] representing the foreground alpha mask, at
the original image resolution.

Usage:
    from models.tools.image_matting.rmbg import RMBGModel
    model = RMBGModel(model_path="briaai/RMBG-1.4")
    mask = model.infer(image)          # HxW float32 in [0, 1]
    rgba = model.remove_background(image)
"""

from typing import Tuple

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from models.tools.base import BaseToolModel


class RMBGModel(BaseToolModel):
    """Thin wrapper around BRIA RMBG-1.4 segmentation model."""

    def __init__(
        self,
        model_path: str = "briaai/RMBG-1.4",
        device: str = "cuda",
        input_size: Tuple[int, int] = (1024, 1024),
        lazy: bool = False,
    ):
        self.input_size = input_size
        super().__init__(model_path=model_path, device=device, lazy=lazy)

    def _load(self) -> None:
        from transformers import AutoModelForImageSegmentation

        self.model = AutoModelForImageSegmentation.from_pretrained(
            self.model_path, trust_remote_code=True
        ).to(self.device).eval()

    # ------------------------------------------------------------------
    # Pre / post processing (matches the official RMBG-1.4 example)
    # ------------------------------------------------------------------

    @staticmethod
    def _preprocess(im: np.ndarray, model_input_size: Tuple[int, int]) -> torch.Tensor:
        from torchvision.transforms.functional import normalize

        if im.ndim < 3:
            im = im[:, :, np.newaxis]
        im_tensor = torch.tensor(im, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
        im_tensor = F.interpolate(
            im_tensor, size=model_input_size, mode="bilinear", align_corners=False
        )
        image = im_tensor / 255.0
        image = normalize(image, [0.5, 0.5, 0.5], [1.0, 1.0, 1.0])
        return image

    @staticmethod
    def _postprocess(result: torch.Tensor, im_size: Tuple[int, int]) -> np.ndarray:
        # im_size is (H, W)
        result = F.interpolate(result, size=im_size, mode="bilinear", align_corners=False)
        ma = torch.max(result)
        mi = torch.min(result)
        result = (result - mi) / (ma - mi + 1e-8)
        return result.squeeze().cpu().numpy().astype(np.float32)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @torch.no_grad()
    def infer(self, image: Image.Image, **kwargs) -> np.ndarray:
        """
        Run background removal.

        Args:
            image: RGB PIL image.

        Returns:
            HxW float32 numpy array in [0, 1] (foreground alpha mask, original size).
        """
        self._ensure_loaded()
        img = np.array(image.convert("RGB"))
        h, w = img.shape[:2]

        x = self._preprocess(img, self.input_size).to(self.device)
        result = self.model(x)
        # RMBG-1.4 returns a list of multi-scale outputs; the first is the final mask.
        if isinstance(result, (list, tuple)):
            result = result[0]
            if isinstance(result, (list, tuple)):
                result = result[0]
        mask = self._postprocess(result, (h, w))
        return mask

    def remove_background(self, image: Image.Image) -> Image.Image:
        """Return the input image with the inferred mask applied as alpha.

        Args:
            image: Input PIL image; converted to RGBA internally.

        Returns:
            RGBA PIL image at the original resolution.
        """
        mask = self.infer(image)
        rgba = np.array(image.convert("RGBA"))
        rgba[..., 3] = (mask * 255).astype(np.uint8)
        return Image.fromarray(rgba, "RGBA")
