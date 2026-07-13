"""
QwenEditModel — wrapper for Qwen-Image-Edit image editing model.

Supports explicit unload() to free VRAM before launching LTX (which itself
takes tens of GB). Recommended pipeline: build images → unload qwen → run LTX.
"""

import gc

import torch
from diffusers import QwenImageEditPlusPipeline
from PIL import Image


class QwenEditModel:
    """Thin wrapper around QwenImageEditPlusPipeline."""

    def __init__(self, model_path: str, device: str = "cuda"):
        dtype = torch.bfloat16 if (device == "cuda" and torch.cuda.is_bf16_supported()) else torch.float32
        self.model_path = model_path
        self.dtype = dtype
        self.device = device
        self.pipe = None
        self.load()

    def load(self):
        """Load (or reload) the pipeline onto self.device."""
        if self.pipe is None:
            self.pipe = QwenImageEditPlusPipeline.from_pretrained(
                self.model_path, torch_dtype=self.dtype,
            ).to(self.device)

    def unload(self):
        """Free VRAM. Safe to call multiple times."""
        if self.pipe is not None:
            try:
                self.pipe.to("cpu")
            except Exception:
                pass
            del self.pipe
            self.pipe = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    def edit(self, image: Image.Image, prompt: str, seed: int = 42, steps: int = 40) -> Image.Image:
        """Run image editing inference."""
        if self.pipe is None:
            self.load()
        with torch.inference_mode():
            result = self.pipe(
                image=[image],
                prompt=prompt,
                generator=torch.Generator(device=self.device).manual_seed(seed),
                true_cfg_scale=4.0,
                num_inference_steps=steps,
                guidance_scale=1.0,
                num_images_per_prompt=1,
            ).images[0]
        return result
