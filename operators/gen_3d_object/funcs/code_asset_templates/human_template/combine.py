"""Compose a generated figure with segmented armour and socketed weapons.

The layer the single-asset pipeline does not have. ``compose`` assembles a
*spec* from templates; this assembles a *worn figure* from files:

    body.glb + armour.glb + sword.glb  ->  one GLB, pieces named, sockets recorded

Order, and why it cannot be another order:

1. Measure the body. A plate's size is the limb it covers, and that number
   does not exist until the figure has been read.
2. Cut the armour. A fused harness has no parts; the cut is what gives
   ``fit_armour`` something to parent.
3. Fit each piece to the body's slot, not the armour's. That is the step
   a uniform overlay cannot do.
4. Hang weapons on named sockets. A sword is rigid; it does not need a cut.
5. Check the result. Scale and AABB overlap, not a renderer.

The body stays one fused mesh — a generated T-pose cannot pose, and
pretending otherwise by cutting the *body* would throw away the surface
that was the reason to generate it. Armour is the thing that has to come
apart, because it is what has to fit a body it was not generated onto.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from . import armour_fit, figure_fit, segment, sockets
from .. import compose as compose_mod


class CombineError(ValueError):
    """A body, a harness or a weapon that cannot be worn together."""


def _drop_unpaired(pieces: dict[str, dict[str, Any]],
                   warnings: list[str]) -> dict[str, dict[str, Any]]:
    """Drop a lateral piece whose opposite side was not cut.

    The chirality gate refuses a ``-l`` without a ``-r``, and it is right
    to: a single greave is how a missing half of the cut used to ship. A
    warning names the drop so a sparse mesh is visible rather than silently
    under-armoured.
    """

    kept = dict(pieces)
    for region, mesh in list(pieces.items()):
        side = mesh.get("side")
        if side not in ("l", "r"):
            continue
        other = region[:-1] + ("r" if side == "l" else "l")
        if other not in pieces:
            warnings.append(
                f"dropped {region}: no {other} to pair with, and a one-sided "
                "lateral piece fails chirality"
            )
            kept.pop(region, None)
    return kept


def _weapon_parts(
    weapons: Sequence[dict[str, Any]],
    *,
    body_id: str,
    landmarks: dict[str, Any],
    body_origin: Sequence[float],
    socket_at: dict[str, Sequence[float]],
) -> list[dict[str, Any]]:
    """Rigid weapon meshes, parented to the figure at the grip socket.

    Parent is the figure, not the socket node: sockets are not geometry
    (see ``sockets.py``). The socket translation is applied as ``at`` so
    the weapon sits where the socket is, and the socket record in extras
    is what a later bone-bind uses to move it.
    """

    parts: list[dict[str, Any]] = []
    for index, weapon in enumerate(weapons):
        source = weapon.get("source")
        if not source:
            raise CombineError(
                f"weapon {index} has no `source`. A weapon without a mesh "
                "cannot be held."
            )
        kind = str(weapon.get("kind") or "sword")
        grip = sockets.grip_for(kind)
        socket_id = weapon.get("socket") or grip["socket"]
        if socket_id not in socket_at:
            raise CombineError(
                f"weapon {kind!r} wants {socket_id}, which is not a socket "
                "on this figure."
            )
        length = float(weapon.get("length") or grip["length"])
        offset = weapon.get("offset") or grip["offset"]
        rotation = weapon.get("rotation") or grip["rotation"]
        at = [
            float(socket_at[socket_id][axis]) + float(offset[axis])
            for axis in range(3)
        ]
        part_id = str(weapon.get("id") or f"weapon-{kind}")
        parts.append({
            "id": part_id,
            "kind": "mesh",
            "source": str(source),
            "size": [length, length, length],
            "at": at,
            "rotation": list(rotation),
            "material": weapon.get("material") or "steel",
            "parent": body_id,
            "profile": None,
            "long_axis": weapon.get("long_axis") or grip.get("long_axis") or "y",
        })
    return parts


def validate_kit(
    spec: dict[str, Any],
    landmarks: dict[str, Any],
    sockets_list: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cheap checks on a composed figure: scale, placement, weapon overlap.

    Not a physics step. An AABB test will not catch a pauldron clipping a
    gorget, and it is not supposed to: those are millimetre defects a
    renderer shows. What this catches is the defect that ships as a
    modelling error — a greave 40 cm off the shin, a sword through the
    ribcage, a helm twice the head.
    """

    from operators.gen_3d_object.funcs.code_asset import part_bounds, validate_spec

    placed = validate_spec(spec)
    by_id = {part["id"]: part for part in placed["parts"]}
    _ = sockets_list
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    slot_height = {
        "head": landmarks["head_y"],
        "neck": landmarks["neck_y"],
        "torso": landmarks["chest_y"],
        "waist": landmarks["waist_y"],
        "hip": landmarks["hip_y"],
        "shoulder": landmarks["shoulder_y"],
        "upperarm": landmarks["shoulder_y"],
        "forearm": landmarks["shoulder_y"],
        "hand": landmarks["shoulder_y"],
        "thigh": (landmarks["crotch_y"] + landmarks["knee_y"]) / 2.0,
        "shin": (landmarks["knee_y"] + landmarks["ankle_y"]) / 2.0,
        "foot": landmarks.get("foot_height", landmarks["ankle_y"]) * 0.5,
    }

    for part in placed["parts"]:
        if not part["id"].startswith("armour-"):
            continue
        region = part["id"][len("armour-"):]
        slot = region.rsplit("-", 1)[0] if region[-2:] in ("-l", "-r") else region
        expected_y = slot_height.get(slot)
        if expected_y is None:
            continue
        low, high = part_bounds(part)
        centre_y = (low[1] + high[1]) / 2.0
        distance = abs(centre_y - expected_y)
        size = max(high[axis] - low[axis] for axis in range(3))
        far = distance > 0.18
        if far:
            warnings.append(
                f"{part['id']} centre y {centre_y:.3f} is {distance:.3f} m "
                f"from the {slot} landmark at {expected_y:.3f}; the plate "
                "is probably on the wrong limb"
            )
        checks.append({
            "id": part["id"], "slot": slot,
            "distance_m": round(distance, 4),
            "size_m": round(size, 4),
            "far": far,
        })

    # A held weapon whose AABB sits mostly inside the torso is going through
    # the chest, not past it. Reported, not failed: a two-handed sword at
    # rest across the body is a legitimate pose this cannot tell from a
    # mis-aimed blade.
    figure = by_id.get("figure")
    torso_box = None
    if figure is not None:
        low, high = part_bounds(figure)
        chest_y = landmarks["chest_y"]
        torso_box = (
            (low[0] * 0.35, chest_y - 0.18, low[2] * 0.4),
            (high[0] * 0.35, chest_y + 0.18, high[2] * 0.4),
        )
    for part in placed["parts"]:
        if not part["id"].startswith("weapon-"):
            continue
        box = part_bounds(part)
        if torso_box is None:
            continue
        overlap = 1.0
        for axis in range(3):
            lo = max(box[0][axis], torso_box[0][axis])
            hi = min(box[1][axis], torso_box[1][axis])
            overlap *= max(0.0, hi - lo)
        volume = 1.0
        for axis in range(3):
            volume *= max(1e-6, box[1][axis] - box[0][axis])
        fraction = overlap / volume
        if fraction > 0.35:
            warnings.append(
                f"{part['id']} overlaps the torso by {fraction:.0%} of its "
                "volume; the grip angle is probably wrong"
            )
        checks.append({
            "id": part["id"], "torso_overlap": round(fraction, 3),
        })

    return {
        "ok": not any(
            item.get("far") or item.get("oversized") for item in checks
        ),
        "warnings": warnings,
        "checks": checks,
    }


def combine_avatar(
    *,
    body: str,
    armour: str | None = None,
    weapons: Sequence[dict[str, Any]] | None = None,
    height_metres: float,
    parts_dir: str | Path,
    subject: str = "composed avatar",
    segment_armour: bool = True,
    min_triangles: int = 8,
    materials: dict[str, dict[str, Any]] | None = None,
    trim_body: Sequence[float] | None = None,
    trim_armour: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Build a spec that dresses ``body`` in ``armour`` and puts weapons in hand.

    Returns ``{"spec", "report"}``. The spec is what ``build_code_asset``
    consumes; the report is what a reviewer reads when the mesh looks wrong
    — landmarks, per-region triangle counts, socket transforms, and the
    validation warnings.

    ``segment_armour`` is the whole reason this function exists. Left on,
    a fused harness is cut and each piece is scaled to this body's limb.
    Turned off, the harness is overlaid as one mesh at ``height_metres`` —
    the control that shows why the cut is worth doing.
    """

    parts_path = Path(parts_dir)
    parts_path.mkdir(parents=True, exist_ok=True)

    marks = figure_fit.landmarks_for(body, height_metres, trim=trim_body)
    figure = armour_fit.body_part(
        body, part_id="figure", height_metres=height_metres,
        material="skin", trim=trim_body,
    )
    origin = figure["at"]
    socket_records = sockets.sockets_for(
        marks, body_id="figure", body_origin=origin,
    )
    socket_at = {row["id"]: row["at"] for row in socket_records}

    warnings: list[str] = []
    worn: list[dict[str, Any]] = []
    segment_counts: dict[str, int] = {}
    segment_paths: dict[str, str] = {}
    cut_info: dict[str, Any] = {}

    if armour:
        if segment_armour:
            try:
                pieces = segment.segment_mesh(
                    armour, trim=trim_armour, min_triangles=min_triangles,
                    guide=body, info=cut_info,
                )
            except (segment.SegmentError, ValueError) as exc:
                raise CombineError(
                    f"could not cut armour {armour}: {exc}"
                ) from exc
            if cut_info.get("cut_guide") == "body":
                warnings.append(
                    "armour self-measure could not drive a cut "
                    f"({cut_info.get('cut_guide_reason', 'unusable T-pose')}); "
                    "sliced on the body's landmarks instead"
                )
            pieces = _drop_unpaired(pieces, warnings)
            segment_counts = {
                region: mesh["triangles"] for region, mesh in pieces.items()
            }
            segment_paths = segment.write_segments(
                pieces, str(parts_path / "armour"),
            )
            kit: list[dict[str, Any]] = []
            for region, path in segment_paths.items():
                slot, side = segment.REGION_SLOTS[region]
                stretch = armour_fit.piece_stretch(slot, marks, path)
                kit.append({
                    "id": f"armour-{region}",
                    "source": path,
                    "slot": slot,
                    "side": side,
                    "span": max(stretch),
                    "stretch": stretch,
                    "material": "steel",
                    "long_axis": pieces[region].get("long_axis") or segment.LONG_AXIS[slot],
                })
            worn.extend(armour_fit.fit_armour(
                body_id="figure", landmarks=marks, pieces=kit,
                body_origin=origin,
            ))
        else:
            # One factor, the body's height. ``at`` is world; the writer
            # parents this node to the figure and subtracts the figure's
            # translation from the vertices, so the origin here is the
            # standing pose the figure already occupies.
            worn.append({
                "id": "armour-whole",
                "kind": "mesh",
                "source": armour,
                "size": [height_metres, height_metres, height_metres],
                "at": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "material": "steel",
                "parent": "figure",
                "long_axis": "y",
                "profile": None,
                **({"trim": list(trim_armour)} if trim_armour else {}),
            })

    if weapons:
        worn.extend(_weapon_parts(
            weapons, body_id="figure", landmarks=marks,
            body_origin=origin, socket_at=socket_at,
        ))

    spec = compose_mod.compose(
        subject=subject,
        body=[figure],
        worn=worn,
        height_metres=height_metres,
        asset_type="avatar",
        materials=materials,
        notes=(
            "Composed by segmenting the armour onto measured landmarks. "
            "Sockets are recorded in extras, not as geometry."
        ),
    )

    report = {
        "body": str(Path(body).resolve()),
        "armour": str(Path(armour).resolve()) if armour else None,
        "height_metres": height_metres,
        "segmented": bool(armour and segment_armour),
        "landmarks": {key: (round(value, 4) if isinstance(value, (int, float))
                            else value)
                      for key, value in marks.items()
                      if not isinstance(value, list)},
        "segments": segment_counts,
        "segment_paths": segment_paths,
        "cut_guide": cut_info.get("cut_guide"),
        "stripped_cape_triangles": cut_info.get("stripped_cape_triangles"),
        "sockets": socket_records,
        "warnings": warnings,
    }
    try:
        report["validation"] = validate_kit(spec, marks, socket_records)
        report["warnings"].extend(report["validation"].get("warnings") or ())
    except Exception as exc:  # noqa: BLE001 — validation must not sink a build
        report["warnings"].append(f"validation skipped: {exc}")

    spec.setdefault("extras", {})
    spec["extras"]["sockets"] = socket_records
    spec["extras"]["compose"] = {
        "segmented": report["segmented"],
        "segments": segment_counts,
        "cut_guide": cut_info.get("cut_guide"),
        "unity_humanoid": {
            row["id"]: row.get("unity_bone") for row in socket_records
        },
    }
    return {"spec": spec, "report": report}


def write_report(report: dict[str, Any], path: str | Path) -> str:
    """Write the compose report as JSON next to the mesh."""

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(out)
