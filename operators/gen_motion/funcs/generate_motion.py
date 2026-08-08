"""Model-agnostic text-to-motion step for ``gen_motion``."""
from __future__ import annotations

from typing import Any


def generate_motion(
    prompt: str,
    model: Any,
    *,
    seed: int = 42,
    motion_length: int = 0,
    use_ik: bool = True,
    in_place: bool = False,
    in_place_lock_height: bool = False,
    repeat_times: int = 1,
    cond_scale: float = 4.0,
    time_steps: int = 18,
    temperature: float = 1.0,
) -> dict:
    """Generate one HumanML3D motion and return in-memory artifacts."""
    return model.infer(
        prompt,
        seed=seed,
        motion_length=motion_length,
        use_ik=use_ik,
        in_place=in_place,
        in_place_lock_height=in_place_lock_height,
        repeat_times=repeat_times,
        cond_scale=cond_scale,
        time_steps=time_steps,
        temperature=temperature,
    )


__all__ = ["generate_motion"]
