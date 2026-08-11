"""
A humanoid you can retarget onto, built from arithmetic.

The motion chain's interesting failures are all structural — auto-mapping needs
a hip junction with three branches, world-delta needs two skeletons whose rest
poses are comparable, the FBX export needs an armature with a baked action —
and none of that can be exercised by the one-bone fixture the unit tests use.
The alternative is committing a rigged character, which means committing
someone's licence terms along with it.

So the fixture is generated: a blocky figure, a Puppeteer-format rig whose
joints sit where its limbs do, and a Mixamo-named BVH with the same topology.
Everything is deterministic, so a failure is the pipeline's and not the
fixture's.

What "the same topology" has to mean
------------------------------------
`mapping_auto` classifies a skeleton by walking it: the hips are the branch
point with three children, the spine is the branch that goes up, the arms hang
off the first branch above it. A fixture that gets that wrong tests nothing but
its own error message. Both skeletons here are built from `HUMANOID`, one
structure, so they agree by construction rather than by my counting twice.

Units and axes
--------------
Both are authored Y-up in metres, which is what glTF uses and what the rig
reader expects — it applies its own Y-up-to-Z-up rotation to rig and mesh
alike, so authoring in Blender's Z-up here would tip the character onto its
face at retarget time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Joint:
    """One joint, its rest position in metres, and what hangs off it."""

    slot: str
    position: tuple[float, float, float]
    children: list["Joint"] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def _joint(slot: str, position, *children: Joint) -> Joint:
    return Joint(slot, position, list(children))


def _limb(side: str, sign: float) -> tuple[Joint, Joint]:
    """One side's arm and leg, mirrored across X by ``sign``."""
    arm = _joint(
        f"{side}_shoulder",
        (0.06 * sign, 1.42, 0.0),
        _joint(
            f"{side}_upper_arm",
            (0.19 * sign, 1.40, 0.0),
            _joint(
                f"{side}_forearm",
                (0.44 * sign, 1.40, 0.0),
                _joint(f"{side}_hand", (0.66 * sign, 1.40, 0.0)),
            ),
        ),
    )
    leg = _joint(
        f"{side}_thigh",
        (0.11 * sign, 0.92, 0.0),
        _joint(
            f"{side}_shin",
            (0.11 * sign, 0.52, 0.0),
            _joint(
                f"{side}_foot",
                (0.11 * sign, 0.09, 0.0),
                _joint(f"{side}_toe", (0.11 * sign, 0.03, 0.13)),
            ),
        ),
    )
    return arm, leg


_LEFT_ARM, _LEFT_LEG = _limb("left", 1.0)
_RIGHT_ARM, _RIGHT_LEG = _limb("right", -1.0)

#: The one skeleton both the rig and the BVH are generated from. A 1.8 m
#: figure: hips at 0.95, head top at 1.72, arms out to 0.66 either side.
HUMANOID = _joint(
    "hips",
    (0.0, 0.95, 0.0),
    _joint(
        "spine",
        (0.0, 1.10, 0.0),
        _joint(
            "spine1",
            (0.0, 1.28, 0.0),
            _joint(
                "neck",
                (0.0, 1.47, 0.0),
                _joint("head", (0.0, 1.60, 0.0)),
            ),
            _LEFT_ARM,
            _RIGHT_ARM,
        ),
    ),
    _LEFT_LEG,
    _RIGHT_LEG,
)

#: Slot -> Mixamo bone name, so the generated clip is something the mapping
#: registry recognises rather than an invented naming scheme.
MIXAMO_NAMES = {
    "hips": "mixamorig:Hips",
    "spine": "mixamorig:Spine",
    "spine1": "mixamorig:Spine1",
    "neck": "mixamorig:Neck",
    "head": "mixamorig:Head",
    "left_shoulder": "mixamorig:LeftShoulder",
    "left_upper_arm": "mixamorig:LeftArm",
    "left_forearm": "mixamorig:LeftForeArm",
    "left_hand": "mixamorig:LeftHand",
    "right_shoulder": "mixamorig:RightShoulder",
    "right_upper_arm": "mixamorig:RightArm",
    "right_forearm": "mixamorig:RightForeArm",
    "right_hand": "mixamorig:RightHand",
    "left_thigh": "mixamorig:LeftUpLeg",
    "left_shin": "mixamorig:LeftLeg",
    "left_foot": "mixamorig:LeftFoot",
    "left_toe": "mixamorig:LeftToeBase",
    "right_thigh": "mixamorig:RightUpLeg",
    "right_shin": "mixamorig:RightLeg",
    "right_foot": "mixamorig:RightFoot",
    "right_toe": "mixamorig:RightToeBase",
}

#: Boxes approximating each body part: slot -> (centre, half-extents). Only
#: the skinning cares about these, and only that each vertex has a nearest
#: joint that is the one a human would pick.
_BLOCKS = {
    "hips": ((0.0, 0.98, 0.0), (0.16, 0.10, 0.10)),
    "spine1": ((0.0, 1.25, 0.0), (0.19, 0.20, 0.11)),
    "head": ((0.0, 1.62, 0.0), (0.10, 0.12, 0.10)),
    "left_upper_arm": ((0.31, 1.40, 0.0), (0.13, 0.06, 0.06)),
    "left_forearm": ((0.55, 1.40, 0.0), (0.12, 0.05, 0.05)),
    "right_upper_arm": ((-0.31, 1.40, 0.0), (0.13, 0.06, 0.06)),
    "right_forearm": ((-0.55, 1.40, 0.0), (0.12, 0.05, 0.05)),
    "left_thigh": ((0.11, 0.72, 0.0), (0.08, 0.20, 0.08)),
    "left_shin": ((0.11, 0.30, 0.0), (0.07, 0.22, 0.07)),
    "left_foot": ((0.11, 0.05, 0.06), (0.07, 0.05, 0.13)),
    "right_thigh": ((-0.11, 0.72, 0.0), (0.08, 0.20, 0.08)),
    "right_shin": ((-0.11, 0.30, 0.0), (0.07, 0.22, 0.07)),
    "right_foot": ((-0.11, 0.05, 0.06), (0.07, 0.05, 0.13)),
}


# ── mesh ──────────────────────────────────────────────────────────────────────


def build_mesh(path: str | Path):
    """
    Write the blocky figure to ``path``; the extension picks the format.

    Boxes are concatenated rather than unioned. A boolean union needs an engine
    that may not be installed, and skinning does not care whether the mesh is
    watertight — it cares that every vertex has a defensible nearest joint.
    """
    import numpy as np
    import trimesh

    parts = []
    for centre, half in _BLOCKS.values():
        box = trimesh.creation.box(
            extents=[value * 2.0 for value in half],
        )
        box.apply_translation(np.asarray(centre, dtype=float))
        parts.append(box)
    mesh = trimesh.util.concatenate(parts)

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(output))
    return output


# ── Puppeteer rig ─────────────────────────────────────────────────────────────


def build_rig(path: str | Path, mesh_path: str | Path) -> Path:
    """
    Write a Puppeteer-format ``.txt`` rig for a mesh built by `build_mesh`.

    Joints are named ``joint0…jointN`` in depth-first order, which is exactly
    what Puppeteer emits and exactly why a bone map cannot be reused between
    characters: the names encode traversal order, not anatomy.

    Every vertex is bound to its nearest joint at full weight. Rigid rather
    than smooth, which is what a blocky figure should deform like anyway, and
    it keeps the fixture free of a weight-painting heuristic that would itself
    need testing.
    """
    import numpy as np
    import trimesh

    joints = list(HUMANOID.walk())
    names = {id(joint): f"joint{index}" for index, joint in enumerate(joints)}

    lines = [
        f"joints {names[id(joint)]} "
        + " ".join(f"{value:.6f}" for value in joint.position)
        for joint in joints
    ]
    lines.append(f"root {names[id(HUMANOID)]}")
    for joint in joints:
        for child in joint.children:
            lines.append(f"hier {names[id(joint)]} {names[id(child)]}")

    mesh = trimesh.load(
        str(mesh_path),
        force="mesh",
        process=False,
        maintain_order=True,
    )
    vertices = np.asarray(mesh.vertices)
    positions = np.asarray([joint.position for joint in joints])
    nearest = np.argmin(
        ((vertices[:, None, :] - positions[None, :, :]) ** 2).sum(axis=2),
        axis=1,
    )
    for index, joint_index in enumerate(nearest):
        lines.append(f"skin {index} {names[id(joints[int(joint_index)])]} 1.0")

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


# ── BVH clip ──────────────────────────────────────────────────────────────────


def build_bvh(
    path: str | Path,
    *,
    frames: int = 12,
    fps: int = 30,
    scale: float = 1.0,
) -> Path:
    """
    Write a Mixamo-named BVH walking on the spot.

    The motion is a sine swing on the hips, thighs and upper arms — enough that
    a retarget which drops a channel, mismatches a side, or bakes an empty
    action is visible in the exported curves rather than merely plausible.

    ``scale`` multiplies every offset, so a caller can produce the
    centimetre-scale file a real Mixamo download would be and check that
    ``global_scale`` puts it back.
    """
    moving = {
        "hips": (0.0, 6.0, 0.0),
        "left_thigh": (0.0, 22.0, 0.0),
        "right_thigh": (0.0, -22.0, 0.0),
        "left_shin": (0.0, -18.0, 0.0),
        "right_shin": (0.0, 18.0, 0.0),
        "left_upper_arm": (0.0, -16.0, 0.0),
        "right_upper_arm": (0.0, 16.0, 0.0),
    }

    ordered: list[Joint] = []
    hierarchy: list[str] = []

    def emit(joint: Joint, parent: Joint | None, depth: int) -> None:
        pad = "  " * depth
        offset = tuple(
            (value - base) * scale
            for value, base in zip(
                joint.position,
                parent.position if parent else (0.0, 0.0, 0.0),
            )
        )
        keyword = "ROOT" if parent is None else "JOINT"
        hierarchy.append(f"{pad}{keyword} {MIXAMO_NAMES[joint.slot]}")
        hierarchy.append(f"{pad}{{")
        hierarchy.append(
            f"{pad}  OFFSET "
            + " ".join(f"{value:.6f}" for value in offset)
        )
        hierarchy.append(
            f"{pad}  CHANNELS 6 Xposition Yposition Zposition "
            "Zrotation Xrotation Yrotation"
            if parent is None
            else f"{pad}  CHANNELS 3 Zrotation Xrotation Yrotation"
        )
        ordered.append(joint)
        for child in joint.children:
            emit(child, joint, depth + 1)
        if not joint.children:
            hierarchy.append(f"{pad}  End Site")
            hierarchy.append(f"{pad}  {{")
            hierarchy.append(f"{pad}    OFFSET 0.000000 {0.10 * scale:.6f} 0.000000")
            hierarchy.append(f"{pad}  }}")
        hierarchy.append(f"{pad}}}")

    emit(HUMANOID, None, 0)

    motion = []
    for frame in range(frames):
        phase = 2.0 * math.pi * frame / max(1, frames - 1)
        values: list[str] = []
        for joint in ordered:
            swing = moving.get(joint.slot)
            angles = (
                tuple(amount * math.sin(phase) for amount in swing)
                if swing
                else (0.0, 0.0, 0.0)
            )
            if joint is HUMANOID:
                # Root translation, so the clip has something for root motion
                # extraction to find on the way out.
                values += [
                    "0.000000",
                    f"{HUMANOID.position[1] * scale:.6f}",
                    f"{0.25 * scale * frame / max(1, frames - 1):.6f}",
                ]
            values += [f"{angle:.6f}" for angle in angles]
        motion.append(" ".join(values))

    text = "\n".join(
        [
            "HIERARCHY",
            *hierarchy,
            "MOTION",
            f"Frames: {frames}",
            f"Frame Time: {1.0 / fps:.6f}",
            *motion,
            "",
        ]
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def build_all(root: str | Path, *, mesh_format: str = ".glb") -> dict[str, str]:
    """Build mesh, rig and clip into one directory and name what landed."""
    directory = Path(root)
    mesh = build_mesh(directory / f"character{mesh_format}")
    rig = build_rig(directory / "character_rig.txt", mesh)
    clip = build_bvh(directory / "walk.bvh")
    return {
        "mesh_path": str(mesh),
        "rig_path": str(rig),
        "motion_path": str(clip),
    }


__all__ = [
    "HUMANOID",
    "MIXAMO_NAMES",
    "Joint",
    "build_all",
    "build_bvh",
    "build_mesh",
    "build_rig",
]
