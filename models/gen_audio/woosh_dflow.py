"""
WooshDFlowModel — thin wrapper for Sony AI's distilled text-to-SFX model.

Reference: https://github.com/SonyResearch/Woosh

Woosh currently distributes weights as release archives. Install the upstream
repository and pass the local ``checkpoints/Woosh-DFlow`` directory as
``model_path``. The public weights are licensed CC-BY-NC.
"""
from __future__ import annotations

import gc
from typing import Any, Optional


class WooshDFlowModel:
    """Wrap Woosh-DFlow text-to-audio inference and return 48 kHz audio."""

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        num_steps: int = 4,
        cfg: float = 4.5,
        renoise: Optional[list[float]] = None,
        latent_channels: int = 128,
        latent_frames: int = 501,
        lazy: bool = False,
    ):
        self.model_path = model_path
        self.device = device
        self.num_steps = num_steps
        self.cfg = cfg
        self.renoise = renoise or [0.0, 0.5, 0.5, 0.3]
        self.latent_channels = latent_channels
        self.latent_frames = latent_frames
        self.lazy = lazy
        self.model: Any = None
        self._sample_euler: Any = None
        if not lazy:
            self.load()

    def load(self) -> None:
        """Load or reload Woosh-DFlow from a local checkpoint directory."""
        if self.model is not None:
            return
        try:
            from woosh.components.base import LoadConfig
            from woosh.inference.flowmap_sampler import sample_euler
            from woosh.model.flowmap_from_pretrained import FlowMapFromPretrained
        except ImportError as exc:
            raise RuntimeError(
                "Sony Woosh is not importable. Clone https://github.com/SonyResearch/Woosh "
                "and install it with `uv sync --extra cuda` (or `--extra cpu`), then "
                "run AAAGameForge from that environment."
            ) from exc

        self.model = FlowMapFromPretrained(LoadConfig(path=self.model_path))
        self.model = self.model.eval().to(self.device)
        self._sample_euler = sample_euler

    def infer(
        self,
        prompt: str,
        seed: int = 42,
        duration_sec: Optional[float] = None,
        num_steps: Optional[int] = None,
        cfg: Optional[float] = None,
    ) -> dict[str, Any]:
        """Generate one sound-effect clip.

        Args:
            prompt: Natural-language sound description.
            seed: Sampling seed.
            duration_sec: Optional upper bound; the native fixed-length result is
                trimmed when this value is shorter. Longer requests are not padded.
            num_steps: Override the distilled sampler step count.
            cfg: Override classifier-free guidance.

        Returns:
            ``{"waveform": float32 ndarray[C, T], "sample_rate": 48000}``.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Woosh-DFlow requires a non-empty sound-effect prompt.")
        if self.model is None:
            self.load()

        import torch

        generator = torch.Generator(device=self.device).manual_seed(seed)
        noise = torch.randn(
            1,
            self.latent_channels,
            self.latent_frames,
            device=self.device,
            generator=generator,
        )
        cond = self.model.get_cond(
            {"audio": None, "description": [prompt]},
            no_dropout=True,
            device=self.device,
        )

        steps = int(num_steps if num_steps is not None else self.num_steps)
        guidance = float(cfg if cfg is not None else self.cfg)
        renoise = self.renoise
        if steps != len(renoise):
            renoise = [0.0] * steps

        with torch.inference_mode():
            latents = self._sample_euler(
                model=self.model,
                noise=noise,
                cond=cond,
                num_steps=steps,
                renoise=renoise,
                cfg=guidance,
            )
            waveform = self.model.autoencoder.inverse(latents)[0].float().cpu()

        peak = float(waveform.abs().max()) if waveform.numel() else 0.0
        if peak > 1.0:
            waveform = waveform / peak
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)

        sample_rate = 48_000
        if duration_sec is not None and duration_sec > 0:
            waveform = waveform[..., : int(float(duration_sec) * sample_rate)]
        return {
            "waveform": waveform.numpy(),
            "sample_rate": sample_rate,
        }

    def unload(self) -> None:
        """Release model memory. Safe to call repeatedly; ``infer`` reloads it."""
        if self.model is not None:
            try:
                self.model.to("cpu")
            except (AttributeError, RuntimeError):
                pass
            del self.model
            self.model = None
            self._sample_euler = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
