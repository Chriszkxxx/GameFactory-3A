"""Parametric T-pose fixtures used to build composition datasets.

No generator, no network. A composition pipeline that can only be exercised
on a paid mesh cannot be regression-tested, and the thing we need to prove
— that cutting a fused harness and fitting the pieces beats overlaying it
whole — is a fact about *proportions*, which primitives state exactly.

Two knobs matter, and they are the two a generated body and a generated
harness disagree on:

    height          the figure's own metres
    limb_scale      how much of that height is leg rather than torso

A harness built at 1.60 m with short legs, overlaid on a 1.85 m long-legged
body, is the case a uniform scale cannot save and a per-slot fit can.
"""
from __future__ import annotations

from typing import Any

from models.common.glb_writer import write_spec_glb


def tpose_parts(
    *,
    height: float = 1.80,
    torso_width: float = 0.34,
    torso_depth: float = 0.20,
    arm_length: float = 0.62,
    arm_radius: float = 0.055,
    leg_spread: float = 0.11,
    thigh_length: float | None = None,
    shin_length: float | None = None,
    material: str = "skin",
) -> list[dict[str, Any]]:
    """A measurable T-pose: arms along x, legs along y.

    Joint heights are fractions of ``height`` so a tall figure and a short
    one keep their proportions unless ``thigh_length`` / ``shin_length``
    override them — which is how two fixtures disagree about where the
    knee is.
    """

    shoulder_y = height * 0.78
    neck_y = height * 0.83
    head_y = height * 0.92
    hip_y = height * 0.44
    # Default knee at 0.27 of height. Overriding shin/thigh is how the
    # armour's knee and the body's knee come apart.
    shin = height * 0.19 if shin_length is None else shin_length
    thigh = height * 0.23 if thigh_length is None else thigh_length
    knee_y = shin + 0.02
    crotch_y = knee_y + thigh
    hip_y = max(hip_y, crotch_y + height * 0.02)

    parts: list[dict[str, Any]] = [
        {"id": "torso", "kind": "box",
         "size": [torso_width, height * 0.33, torso_depth],
         "at": [0.0, (hip_y + shoulder_y) / 2.0, 0.0],
         "material": material},
        {"id": "head", "kind": "sphere",
         "size": [height * 0.11, height * 0.145, height * 0.12],
         "at": [0.0, head_y, 0.0],
         "material": material},
        {"id": "neck", "kind": "cylinder",
         "size": [height * 0.055, height * 0.065, height * 0.055],
         "at": [0.0, neck_y, 0.0],
         "material": material, "segments": 16},
        {"id": "hip", "kind": "box",
         "size": [torso_width * 0.94, height * 0.10, torso_depth],
         "at": [0.0, hip_y, 0.0],
         "material": material},
    ]
    for side, sign in (("l", -1.0), ("r", 1.0)):
        parts += [
            {"id": f"arm-{side}", "kind": "cylinder",
             "size": [arm_length, arm_radius * 2, arm_radius * 2],
             "at": [sign * (torso_width / 2.0 + arm_length / 2.0),
                    shoulder_y, 0.0],
             "rotation": [0.0, 0.0, 90.0],
             "material": material, "segments": 16},
            {"id": f"thigh-{side}", "kind": "cylinder",
             "size": [leg_spread * 1.45, thigh, leg_spread * 1.45],
             "at": [sign * leg_spread, knee_y + thigh / 2.0, 0.0],
             "material": material, "segments": 16},
            {"id": f"shin-{side}", "kind": "cylinder",
             "size": [leg_spread * 1.1, shin, leg_spread * 1.1],
             "at": [sign * leg_spread, shin / 2.0 + 0.01, 0.0],
             "material": material, "segments": 16},
        ]
    return parts


def armour_shell_parts(
    *,
    height: float = 1.70,
    bulk: float = 1.18,
    **body_kwargs: Any,
) -> list[dict[str, Any]]:
    """A fused-looking harness: the same T-pose, thicker, in steel.

    ``bulk`` scales radial sizes so the shell stands off the skin. Joint
    heights follow ``height`` (and any thigh/shin override), which is how
    this harness and a body of a different proportion disagree.
    """

    kwargs = dict(body_kwargs)
    kwargs.setdefault("torso_width", 0.34 * bulk)
    kwargs.setdefault("torso_depth", 0.20 * bulk)
    kwargs.setdefault("arm_radius", 0.055 * bulk)
    kwargs.setdefault("leg_spread", 0.11 * bulk)
    parts = tpose_parts(height=height, material="steel", **kwargs)
    # Names stay unique so a later flatten still has one mesh per node;
    # the reader then welds them into the fused surface the cut expects.
    for part in parts:
        part["id"] = f"plate-{part['id']}"
    return parts


def sword_parts(*, length: float = 1.05) -> list[dict[str, Any]]:
    """A longsword standing on y, grip near the origin."""

    blade = length * 0.72
    return [
        {"id": "blade", "kind": "box",
         "size": [0.045, blade, 0.012],
         "at": [0.0, blade / 2.0 + 0.04, 0.0],
         "material": "blade", "chamfer": 0.2},
        {"id": "guard", "kind": "box",
         "size": [0.18, 0.02, 0.04],
         "at": [0.0, 0.03, 0.0],
         "material": "brass"},
        {"id": "grip", "kind": "cylinder",
         "size": [0.028, 0.11, 0.028],
         "at": [0.0, -0.04, 0.0],
         "material": "leather", "segments": 12},
        {"id": "pommel", "kind": "sphere",
         "size": [0.044, 0.040, 0.044],
         "at": [0.0, -0.11, 0.0],
         "material": "brass", "segments": 12},
    ]


def shield_parts(*, height: float = 0.70) -> list[dict[str, Any]]:
    return [
        {"id": "face", "kind": "box",
         "size": [0.42, height, 0.03],
         "at": [0.0, height / 2.0, 0.0],
         "material": "shieldFace", "chamfer": 0.2},
        {"id": "boss", "kind": "sphere",
         "size": [0.10, 0.08, 0.08],
         "at": [0.0, height * 0.55, 0.04],
         "material": "brass", "segments": 12},
    ]


_MATERIALS = {
    "skin": {"baseColor": [0.86, 0.71, 0.62, 1.0], "roughness": 0.52},
    "steel": {"baseColor": [0.62, 0.64, 0.68, 1.0], "metallic": 1.0, "roughness": 0.24},
    "blade": {"baseColor": [0.78, 0.80, 0.84, 1.0], "metallic": 1.0, "roughness": 0.12},
    "brass": {"baseColor": [0.72, 0.55, 0.22, 1.0], "metallic": 1.0, "roughness": 0.28},
    "leather": {"baseColor": [0.22, 0.13, 0.09, 1.0], "roughness": 0.78},
    "shieldFace": {"baseColor": [0.36, 0.08, 0.11, 1.0], "roughness": 0.44},
}


def _write(subject: str, parts: list[dict[str, Any]],
           path: str, height: float) -> str:
    from operators.gen_3d_object.funcs.code_asset import validate_spec

    used = {part.get("material", "default") for part in parts}
    spec = validate_spec({
        "subject": subject,
        "units": "metres",
        "forward": "+z",
        "asset_type": "avatar" if "body" in subject or "armour" in subject else "weapon",
        "height_metres": height,
        "materials": {name: _MATERIALS[name] for name in used if name in _MATERIALS},
        "parts": parts,
    })
    return write_spec_glb(spec, path)


#: Named bodies / harnesses / weapons the batch runner cross-combines.
BODIES: dict[str, dict[str, Any]] = {
    # Long-legged, 1.85 m — the figure a short harness has to be *fitted* to.
    "tall": {"height": 1.85, "thigh_length": 0.48, "shin_length": 0.40,
             "torso_width": 0.32, "leg_spread": 0.13},
    # Compact, 1.62 m, wider torso.
    "stocky": {"height": 1.62, "thigh_length": 0.32, "shin_length": 0.28,
               "torso_width": 0.40, "torso_depth": 0.24, "leg_spread": 0.12},
    # Nominal 1.80 m, the fixture the existing tests already measure.
    "nominal": {"height": 1.80},
}

ARMOURS: dict[str, dict[str, Any]] = {
    # Built for a shorter, shorter-legged wearer.
    "short_plate": {"height": 1.58, "thigh_length": 0.30, "shin_length": 0.24,
                    "bulk": 1.22},
    # Built for a taller wearer, bulkier plates.
    "tall_plate": {"height": 1.88, "thigh_length": 0.50, "shin_length": 0.42,
                   "bulk": 1.16},
}

WEAPONS: dict[str, dict[str, Any]] = {
    "sword": {"kind": "sword", "builder": sword_parts, "height": 1.05},
    "shield": {"kind": "shield", "builder": shield_parts, "height": 0.70},
}


def write_library(out_dir: str) -> dict[str, dict[str, str]]:
    """Write every named fixture and return {bodies, armours, weapons} paths."""

    from pathlib import Path

    root = Path(out_dir)
    library: dict[str, dict[str, str]] = {"bodies": {}, "armours": {}, "weapons": {}}

    for name, kwargs in BODIES.items():
        height = kwargs["height"]
        library["bodies"][name] = _write(
            f"body {name}", tpose_parts(**kwargs),
            str(root / "bodies" / f"{name}.glb"), height,
        )
    for name, kwargs in ARMOURS.items():
        height = kwargs["height"]
        bulk = kwargs.get("bulk", 1.18)
        extra = {k: v for k, v in kwargs.items() if k not in ("height", "bulk")}
        library["armours"][name] = _write(
            f"armour {name}", armour_shell_parts(height=height, bulk=bulk, **extra),
            str(root / "armours" / f"{name}.glb"), height,
        )
    for name, meta in WEAPONS.items():
        library["weapons"][name] = _write(
            name, meta["builder"](height=meta["height"]) if name == "shield"
            else meta["builder"](length=meta["height"]),
            str(root / "weapons" / f"{name}.glb"), meta["height"],
        )
    return library
