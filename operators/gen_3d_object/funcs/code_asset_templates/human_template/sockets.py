"""Named sockets on a measured figure.

A socket is a transform bound to a slot: the empty node a weapon or a plate
parents to. Because it is computed from the same ``slot_position`` the
plate uses, the two cannot drift. The names follow the convention in the
composition plan so a later Puppeteer / Unity Humanoid pass can reparent
each socket onto a bone without renaming anything here.

    Socket_Weapon_R  ->  hand / right   (Unity: RightHand)
    Socket_Chest     ->  torso          (Unity: Chest)
    Socket_Shin_L    ->  shin / left    (Unity: LeftLowerLeg)

Phase one parents every socket to the fused figure. The figure cannot pose,
so the sockets do not yet follow individual limbs — they follow the root.
The names and translations are what the retarget step consumes once a
skeleton exists: reparent ``Socket_Shin_L`` onto ``LeftLowerLeg`` and the
greave already sitting on that socket swings with the calf.
"""
from __future__ import annotations

from typing import Any, Sequence

from .armour_fit import slot_position

#: Unity Humanoid bone each slot maps onto, so the extras in the composed
#: GLB are enough to reparent after a Humanoid import without a second table.
UNITY_HUMANOID: dict[tuple[str, str | None], str] = {
    ("head", None): "Head",
    ("neck", None): "Neck",
    ("torso", None): "Chest",
    ("waist", None): "Spine",
    ("hip", None): "Hips",
    ("shoulder", "l"): "LeftShoulder",
    ("shoulder", "r"): "RightShoulder",
    ("upperarm", "l"): "LeftUpperArm",
    ("upperarm", "r"): "RightUpperArm",
    ("forearm", "l"): "LeftLowerArm",
    ("forearm", "r"): "RightLowerArm",
    ("hand", "l"): "LeftHand",
    ("hand", "r"): "RightHand",
    ("thigh", "l"): "LeftUpperLeg",
    ("thigh", "r"): "RightUpperLeg",
    ("shin", "l"): "LeftLowerLeg",
    ("shin", "r"): "RightLowerLeg",
    ("foot", "l"): "LeftFoot",
    ("foot", "r"): "RightFoot",
}

#: Canonical sockets. A kit that needs an extra one (a quiver on the hip, a
#: banner on the back) passes ``extra`` to :func:`sockets_for` rather than
#: editing this table.
SOCKETS: dict[str, dict[str, Any]] = {
    "Socket_Weapon_R": {"slot": "hand", "side": "r"},
    "Socket_Weapon_L": {"slot": "hand", "side": "l"},
    "Socket_Chest": {"slot": "torso"},
    "Socket_Back": {"slot": "torso", "offset": (0.0, 0.04, -0.08)},
    "Socket_Head": {"slot": "head"},
    "Socket_Neck": {"slot": "neck"},
    "Socket_Hip": {"slot": "hip"},
    "Socket_Shoulder_L": {"slot": "shoulder", "side": "l"},
    "Socket_Shoulder_R": {"slot": "shoulder", "side": "r"},
    "Socket_Upperarm_L": {"slot": "upperarm", "side": "l"},
    "Socket_Upperarm_R": {"slot": "upperarm", "side": "r"},
    "Socket_Forearm_L": {"slot": "forearm", "side": "l"},
    "Socket_Forearm_R": {"slot": "forearm", "side": "r"},
    "Socket_Thigh_L": {"slot": "thigh", "side": "l"},
    "Socket_Thigh_R": {"slot": "thigh", "side": "r"},
    "Socket_Shin_L": {"slot": "shin", "side": "l"},
    "Socket_Shin_R": {"slot": "shin", "side": "r"},
    "Socket_Foot_L": {"slot": "foot", "side": "l"},
    "Socket_Foot_R": {"slot": "foot", "side": "r"},
}

#: Grip templates: rotation (XYZ degrees) and a small offset from the hand
#: socket so a blade does not start inside the palm. Chosen for a T-pose
#: with +y up and +z forward; a later retarget keeps the local offset.
WEAPON_GRIPS: dict[str, dict[str, Any]] = {
    "sword": {
        "socket": "Socket_Weapon_R",
        # Blade is authored along +y. On a T-pose the right arm runs along
        # +x, so -90 about z puts the blade in the hand's own direction
        # instead of sticking past the crown and blowing the scale gate.
        "rotation": (0.0, 0.0, -90.0),
        "offset": (0.04, 0.0, 0.02),
        "length": 1.05,
        "long_axis": "x",
    },
    "axe": {
        "socket": "Socket_Weapon_R",
        "rotation": (0.0, 0.0, -90.0),
        "offset": (0.03, 0.0, 0.02),
        "length": 0.80,
        "long_axis": "x",
    },
    "spear": {
        "socket": "Socket_Weapon_R",
        "rotation": (0.0, 0.0, -90.0),
        "offset": (0.06, 0.0, 0.03),
        "length": 1.80,
        "long_axis": "x",
    },
    "bow": {
        "socket": "Socket_Weapon_L",
        "rotation": (0.0, 90.0, 0.0),
        "offset": (0.0, 0.02, 0.04),
        "length": 1.20,
        "long_axis": "y",
    },
    "shield": {
        "socket": "Socket_Weapon_L",
        "rotation": (0.0, 80.0, 0.0),
        "offset": (-0.06, 0.10, -0.03),
        "length": 0.70,
        "long_axis": "y",
    },
}


def socket_name(slot: str, side: str | None = None) -> str:
    """The canonical socket id for a slot/side pair."""

    for name, row in SOCKETS.items():
        if row["slot"] == slot and row.get("side") == side:
            return name
    suffix = f"_{side.upper()}" if side else ""
    return f"Socket_{slot.capitalize()}{suffix}"


def sockets_for(
    landmarks: dict[str, Any],
    *,
    body_id: str,
    body_origin: Sequence[float] | None = None,
    extra: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Socket records: id, translation in the figure's frame, bone hint.

    These are data, not spec parts. Writing them as geometry would put a
    1 cm cube at every joint that the solidity gate then has to special-case
    and that a renderer would draw. They travel in ``sockets.json`` and in
    the GLB extras so a later pass can materialise them as empty nodes.
    """

    table = {**SOCKETS, **(extra or {})}
    out: list[dict[str, Any]] = []
    for name, row in table.items():
        slot = row["slot"]
        side = row.get("side")
        at = slot_position(
            slot, landmarks,
            side=side,
            offset=row.get("offset"),
            body_origin=body_origin,
        )
        out.append({
            "id": name,
            "slot": slot,
            "side": side,
            "parent": body_id,
            "at": [round(value, 6) for value in at],
            "rotation": [0.0, 0.0, 0.0],
            "unity_bone": UNITY_HUMANOID.get((slot, side)),
        })
    return out


def grip_for(kind: str) -> dict[str, Any]:
    """The grip template for a weapon kind, or a refusal by name."""

    row = WEAPON_GRIPS.get(kind.lower())
    if row is None:
        known = ", ".join(sorted(WEAPON_GRIPS))
        raise ValueError(
            f"unknown weapon kind {kind!r}. Known: {known}. "
            "A missing template would place the weapon at the origin, "
            "which reads as a modelling error rather than a spec one."
        )
    return dict(row)
