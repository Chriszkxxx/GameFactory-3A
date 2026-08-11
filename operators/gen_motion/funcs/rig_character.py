"""Model-agnostic character rigging step for ``gen_motion``."""
from __future__ import annotations

from typing import Any


def rig_character(
    mesh: bytes,
    model: Any,
    *,
    mesh_format: str = ".glb",
    seed: int = 42,
    post_filter: bool = True,
) -> dict:
    """Return Puppeteer-compatible rig artifacts as in-memory values."""
    return model.infer(
        mesh,
        mesh_format=mesh_format,
        seed=seed,
        post_filter=post_filter,
    )


__all__ = ["rig_character"]
