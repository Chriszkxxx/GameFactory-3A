"""
QwenEditModel — wrapper for the Qwen-Image-Edit instruction-guided image editor.

Reference: https://huggingface.co/Qwen/Qwen-Image-Edit-2511

Needs a CUDA GPU for practical speed; `device="cpu"` works but is very slow.
`unload()` frees the VRAM before a second heavy model is loaded (e.g. LTX),
so the recommended order is: build images -> unload() -> run the video model.

Usage:
    from models.gen_image.qwen_edit_model import QwenEditModel
    model = QwenEditModel(model_path="Qwen/Qwen-Image-Edit-2511")
    out = model.infer(image, prompt="make it a T-pose", seed=42)
"""

import gc

from PIL import Image


class QwenEditModel:
    """Thin wrapper around `QwenImageEditPlusPipeline` (image -> edited image)."""

    def __init__(self, model_path: str, device: str = "cuda"):
        """
        Args:
            model_path: Local path or HuggingFace repo id of the Qwen-Image-Edit weights.
            device:     Inference device, "cuda" or "cpu".
        """
        self.model_path = model_path
        self.device = device
        self.pipe = None
        self.load()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load (or reload) the pipeline onto `self.device`. Idempotent."""
        if self.pipe is not None:
            return

        import torch
        from diffusers import QwenImageEditPlusPipeline

        self.dtype = (
            torch.bfloat16
            if (self.device == "cuda" and torch.cuda.is_bf16_supported())
            else torch.float32
        )
        self.pipe = QwenImageEditPlusPipeline.from_pretrained(
            self.model_path, torch_dtype=self.dtype,
        ).to(self.device)

    def unload(self) -> None:
        """Free VRAM. Idempotent — safe after a failed load and safe to repeat."""
        if getattr(self, "pipe", None) is not None:
            try:
                self.pipe.to("cpu")
            except Exception:
                pass
            del self.pipe
            self.pipe = None
        gc.collect()
        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def infer(
        self,
        image: Image.Image,
        prompt: str,
        seed: int = 42,
        steps: int = 40,
    ) -> Image.Image:
        """
        Run instruction-guided image editing.

        Args:
            image:  Input PIL image (any mode; the pipeline handles conversion).
            prompt: Edit instruction.
            seed:   Random seed; the same (image, prompt, seed) reproduces the output.
            steps:  Number of diffusion steps.

        Returns:
            The edited PIL image (RGB), at the pipeline's native resolution.
        """
        import torch

        if self.pipe is None:
            self.load()
        with torch.inference_mode():
            return self.pipe(
                image=[image],
                prompt=prompt,
                generator=torch.Generator(device=self.device).manual_seed(seed),
                true_cfg_scale=4.0,
                num_inference_steps=steps,
                guidance_scale=1.0,
                num_images_per_prompt=1,
            ).images[0]

    def edit(
        self,
        image: Image.Image,
        prompt: str,
        seed: int = 42,
        steps: int = 40,
    ) -> Image.Image:
        """Compatibility alias; production operators use the canonical `infer()`."""
        return self.infer(image, prompt=prompt, seed=seed, steps=steps)
