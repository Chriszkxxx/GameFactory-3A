"""
Text to a humanoid clip, in whatever model was injected.

The step is deliberately a thin pass to ``model.infer`` — the operator owns the
paths and the model owns the sampling, so there is nothing left in between
except the part worth keeping: refusing input the model would silently accept,
and refusing output the next stage would silently mis-handle.

What comes back
---------------
A dict of in-memory artifacts, never files. ``bvh_bytes`` is the clip the rest
of the pipeline retargets; ``raw_bvh_bytes`` and ``ik_bvh_bytes`` are the same
motion before and after foot-contact cleanup, kept because comparing them is
how you tell a sliding foot from a bad mapping. ``joints`` is the raw joint
array and ``preview_mp4_bytes`` a stick-figure render — both optional, both
worth writing out when present, because they are what makes a bad clip
diagnosable without opening Blender.

``fps`` is the one field a caller must not assume. HumanML3D models sample at
20 fps, not 30, and a clip retargeted at the wrong rate is not wrong in any way
that looks wrong — it just plays at the wrong speed. Read it from the result.
"""
from __future__ import annotations

from typing import Any


#: HumanML3D's sampling rate, and so MoMask's. Only a fallback: a model that
#: reports its own rate is believed over this.
DEFAULT_FPS = 20


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
    """
    Generate one clip from a text prompt.

    Args:
        prompt: What the character does, in a plain sentence. HumanML3D was
            captioned that way ("a person walks forward and waves"), so a
            prompt written as tags reads as out-of-distribution to the model.
        model: Anything with MoMask's ``infer`` signature.
        seed: Fixes the sample. The same seed and prompt give the same clip.
        motion_length: Frames to generate; 0 lets the model's length estimator
            choose. Note **frames, not seconds** — at 20 fps, 40 is two.
        use_ik: Run the foot-contact pass. Off gives the raw sample, which
            slides; on is what should reach a game.
        in_place: Strip root translation, leaving a clip that animates on the
            spot. What you want when the game's own locomotion moves the
            character and the clip only has to look like walking.
        in_place_lock_height: Also pin the root height. Locks out crouches and
            jumps, so only for flat locomotion.
        repeat_times: Draw several samples; the model picks one to return.
        cond_scale: Classifier-free guidance. Higher follows the prompt more
            literally and moves less naturally.
        time_steps: Denoising iterations for the residual stage.
        temperature: Sampling temperature.

    Returns:
        The model's artifact dict, guaranteed to carry non-empty ``bvh_bytes``
        and an integer ``fps``.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("generate_motion needs a non-empty text prompt.")
    if motion_length < 0:
        raise ValueError(f"motion_length must be >= 0, got {motion_length}")
    if repeat_times < 1:
        raise ValueError(f"repeat_times must be >= 1, got {repeat_times}")

    artifacts = model.infer(
        prompt.strip(),
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
    if not isinstance(artifacts, dict):
        raise RuntimeError(
            "Text-to-motion model returned "
            f"{type(artifacts).__name__}, expected a dict of artifacts."
        )
    if not artifacts.get("bvh_bytes"):
        raise RuntimeError(
            "Text-to-motion model returned no BVH. Nothing downstream can "
            f"retarget this result; keys present: {sorted(artifacts)}"
        )
    artifacts.setdefault("fps", DEFAULT_FPS)
    return artifacts


__all__ = ["DEFAULT_FPS", "generate_motion"]
