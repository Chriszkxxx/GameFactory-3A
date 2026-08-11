"""
A static mesh in, a skeleton and skin weights out.

Like ``generate_motion`` this is a thin pass to an injected model, and for the
same reason: the operator owns the paths, the model owns the prediction. What
is worth doing here is the part that bites downstream — the mesh the rig is
predicted against has to be the mesh the rig is *used* against.

The vertex-order contract
-------------------------
A Puppeteer rig's ``skin`` lines address vertices by index. Those indices are
positions in the mesh the model was handed, so any step that reorders vertices
between rigging and retargeting silently rebinds the skin: the weights still
load, the character still moves, and the deformation is nonsense.

Two things follow. The rigged artifacts include the exact triangulated OBJ the
model consumed, so retargeting has something whose ordering is known. And the
format is passed through rather than converted here, so the conversion happens
once, inside the model, instead of once here and again there.
"""
from __future__ import annotations

from typing import Any


#: What a rigging model is expected to read. GLB is what the 3D-object stage
#: emits; OBJ is what Puppeteer works in internally and what its own rig
#: artifacts are indexed against.
SUPPORTED_MESH_FORMATS = (".glb", ".gltf", ".obj", ".ply", ".stl")


def normalise_mesh_format(value: str) -> str:
    """Return a validated lower-case mesh extension with its leading dot."""
    ext = str(value).lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext not in SUPPORTED_MESH_FORMATS:
        raise ValueError(
            f"mesh_format must be one of {', '.join(SUPPORTED_MESH_FORMATS)}, "
            f"got {value!r}"
        )
    return ext


def rig_character(
    mesh: bytes,
    model: Any,
    *,
    mesh_format: str = ".glb",
    seed: int = 42,
    post_filter: bool = True,
) -> dict:
    """
    Predict a skeleton and skin weights for one character mesh.

    Args:
        mesh: The complete mesh file, as bytes.
        model: Anything with Puppeteer's ``infer`` signature.
        mesh_format: Extension telling the model how to read ``mesh``.
        seed: Forwarded to both the skeleton and the skinning stage.
        post_filter: Smooth weights across each vertex's one-ring neighbours.
            Costs a little sharpness at joints and removes the isolated
            single-vertex spikes that show up as pinched geometry when posed.

    Returns:
        The model's artifact dict, guaranteed to carry ``rig_text``,
        ``skeleton_text`` and ``mesh_obj_bytes``.
    """
    if not isinstance(mesh, (bytes, bytearray)) or not mesh:
        raise ValueError("rig_character needs non-empty mesh file bytes.")

    artifacts = model.infer(
        bytes(mesh),
        mesh_format=normalise_mesh_format(mesh_format),
        seed=seed,
        post_filter=post_filter,
    )
    if not isinstance(artifacts, dict):
        raise RuntimeError(
            "Rigging model returned "
            f"{type(artifacts).__name__}, expected a dict of artifacts."
        )
    missing = [
        key
        for key in ("rig_text", "skeleton_text", "mesh_obj_bytes")
        if not artifacts.get(key)
    ]
    if missing:
        raise RuntimeError(
            f"Rigging model returned no {', '.join(missing)}. Retargeting "
            "needs all three; keys present: " + str(sorted(artifacts))
        )
    return artifacts


__all__ = [
    "SUPPORTED_MESH_FORMATS",
    "normalise_mesh_format",
    "rig_character",
]
