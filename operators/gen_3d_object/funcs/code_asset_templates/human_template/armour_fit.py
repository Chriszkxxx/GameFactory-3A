"""Fit armour onto a measured figure, rather than onto assumed coordinates.

The layer between `figure_fit` and a spec. What it does that a kit template
cannot: a kit says "a greave goes on a shin"; this says *which* shin, *how
big*, and *where* — read from the body that is actually being dressed.

WHY THE BODY IS ONE PART AND THE ARMOUR IS MANY. A generated T-pose figure is
one fused mesh: its limbs are not separable, so it cannot be posed and its
shin cannot be a parent. That is the trade this route makes knowingly. What it
buys is a body that looks like a body — the alternative, a torso built from
lathes, is the programmer art the whole exercise is trying to leave behind,
and `suits_code_asset` routes a figure to `generate` for exactly this reason.

So the armour parents to the *figure*, not to a limb, and the hierarchy is one
level deep. When a rigged body is available the same fitting code applies with
`parent` set per limb instead — the placements are already computed per limb.

WHY PIECES ARE SCALED, NOT AUTHORED TO SIZE. A fetched greave has whatever
proportions the generator gave it. Fitting it means scaling it to the limb it
covers, and `size` on a `mesh` part is a single factor, so a piece is placed by
saying how long it should be along its own longest axis and where its centre
goes. Both come from the measured landmarks.
"""
from __future__ import annotations

from typing import Any, Sequence


def span_to_wrap(source: str, *, girth: float, axis: str = "z",
                 clearance: float = 1.10,
                 trim: Sequence[float] | None = None) -> float:
    """The ``span`` that makes a fetched piece enclose ``girth`` across ``axis``.

    For a plate that wraps a limb or a torso, the size that matters is the
    cross-section, not the length. Sizing the cuirass from shoulder-to-waist
    made it 0.172 m deep around a 0.181 m chest — it sank into the ribcage,
    front and back, which reads as a modelling error and not a fitting one.

    Since ``size`` on a `mesh` part is one factor, asking for a girth is the
    same as asking for a length: it is the piece's own proportion that converts
    between them, and that proportion is read from the file rather than
    assumed. ``clearance`` is the air between plate and skin.

    ``girth`` may be a mapping of axis to girth, in which case the piece is
    sized to whichever axis needs it largest. One factor cannot satisfy two
    axes independently, so the choice is between clearing the body on both and
    clearing it on one: sizing the cuirass to chest *depth* alone left it
    0.382 m wide around a 0.490 m chest, narrower than what it wrapped in the
    axis nobody checked.
    """

    from models.common.glb_writer import load_mesh_asset

    extent = load_mesh_asset(source, trim)["unit_extent"]
    index = {"x": 0, "y": 1, "z": 2}
    wanted = girth if isinstance(girth, dict) else {axis: girth}

    spans = []
    for name, measure in wanted.items():
        across = extent[index[name]]
        if across <= 0:
            raise ValueError(
                f"{source}: no extent along {name}, so nothing to wrap")
        # `span` is measured along the longest axis, so convert girth-across
        # into length-along by the ratio the piece itself has.
        spans.append(measure * clearance * max(extent) / across)
    return max(spans)


#: Where each slot sits on a measured figure.
#:
#: A real table, keyed by slot name. Each row says how to reach the three
#: coordinates from the landmarks: ``lateral`` is the distance out from the
#: centreline (mirrored by side), ``height`` picks the y, and ``depth`` names
#: which of the measured front-to-back centres the piece follows.
#:
#: This was fifteen ``elif`` branches whose own comment claimed to be a table.
#: The difference matters for the reason the comment was reaching for: adding a
#: slot to a table is data, and callers outside this module can add one without
#: editing it. A branch chain can only be extended by whoever owns the file.
#:
#: ``depth`` is a name rather than a number because a body is not flat: the
#: chest and the throat are 0.090 m apart front-to-back on the figure this was
#: measured on, so ``midline`` means "as deep as the body is at this height",
#: read from a profile, rather than one torso depth reused up the whole figure.
#:
#: ``lateral`` has the same escape for the same reason. ``"limb"`` means "as far
#: out as this leg is at this height", read from the measured leg profile — a
#: pair of legs is not a pair of vertical columns, and this figure's splay puts
#: the shin 0.045 m outboard of the thigh. Placing greaves on the single
#: thigh-derived ``leg_x`` sat them inboard of the legs entirely, which rendered
#: as four limbs: two plates hanging between two bare legs.
SLOTS: dict[str, dict[str, Any]] = {
    # --- legs -------------------------------------------------------------
    "shin":     {"lateral": "limb",   "height": ("knee_y", "ankle_y"),
                 "depth": "midline"},
    "thigh":    {"lateral": "limb",   "height": ("crotch_y", "knee_y"),
                 "depth": "midline"},
    "knee":     {"lateral": "limb",   "height": "knee_y", "depth": "midline"},
    # The instep, from the foot's own measured x and z. `ankle_y * 0.6` and
    # `* 0.5` were guesses that looked close on one figure and put the sabaton
    # 0.075 m inboard of the foot and behind the heel.
    "foot":     {"lateral": "foot_x", "height": "instep_y", "depth": "foot_z"},
    # --- midline ----------------------------------------------------------
    "torso":    {"lateral": None, "height": "chest_y",  "depth": "midline"},
    "waist":    {"lateral": None, "height": "waist_y",  "depth": "midline"},
    "hip":      {"lateral": None, "height": "hip_y",    "depth": "midline"},
    "head":     {"lateral": None, "height": "head_y",   "depth": "midline"},
    "neck":     {"lateral": None, "height": "neck_y",   "depth": "midline"},
    # --- arms: a T-pose runs them along x, so a position is a distance out --
    "shoulder": {"lateral": ("shoulder_x", 1.15), "height": "shoulder_y",
                 "depth": "arm_z"},
    "upperarm": {"lateral": ("shoulder_x", "elbow_x"), "height": "shoulder_y",
                 "depth": "arm_z"},
    "elbow":    {"lateral": "elbow_x", "height": "shoulder_y", "depth": "arm_z"},
    "forearm":  {"lateral": ("elbow_x", "wrist_x"), "height": "shoulder_y",
                 "depth": "arm_z"},
    "hand":     {"lateral": "wrist_x", "height": "shoulder_y", "depth": "arm_z"},
}


def _resolve(spec: Any, landmarks: dict[str, Any]) -> float:
    """One coordinate from a table entry.

    A name is looked up, a pair is the midpoint of two names, a name with a
    number scales it, and a number is itself. Four forms because that is what
    the placements need and no more: anything further belongs in the table as
    an explicit landmark rather than as a new kind of expression here.
    """

    if spec is None:
        return 0.0
    if isinstance(spec, (int, float)):
        return float(spec)
    if isinstance(spec, str):
        return float(landmarks[spec])
    first, second = spec
    if isinstance(second, (int, float)) and not isinstance(second, bool):
        return float(landmarks[first]) * float(second)
    return (float(landmarks[first]) + float(landmarks[second])) / 2.0


def fit_armour(
    *,
    body_id: str,
    landmarks: dict[str, Any],
    pieces: Sequence[dict[str, Any]],
    body_origin: Sequence[float] | None = None,
    slots: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Place each piece on the measured body.

    ``pieces`` are descriptions rather than spec parts:

        {"id": "greave-l", "source": "parts/greave.glb", "slot": "shin",
         "side": "l", "span": 0.30, "material": "steel"}

    ``slot`` names where it goes and is what the landmarks are read for;
    ``span`` is how many metres it should occupy along its own longest axis.
    Everything else — position, mirroring, the parent — follows.

    ``slots`` adds rows to :data:`SLOTS` for one call, so a kit that needs a
    placement this module never anticipated — a tail, a backpack, a third arm —
    is supplied by the caller instead of requiring an edit here. The rows are
    the same shape as the built-in ones and are checked the same way.

    ``body_origin`` is the figure's own ``at``, and it is required whenever
    ``body_id`` is given because the two conventions have to be reconciled
    somewhere. Landmarks are absolute heights off the ground; a parented
    part's ``at`` is local to its parent. Producing world coordinates *and*
    naming a parent put both in one part, and every plate came out half a
    body-height too high — the figure's centre, since a normalised mesh is
    centred on its own bounds. Converted here, at the point the placement is
    made, rather than by weakening the resolver's rule.

    Refuses an unknown slot by name. A silently unplaced piece is worse than a
    refusal, because it renders as a plate at the origin inside the figure's
    ankle, which reads as a modelling error rather than a spec error.
    """

    L = dict(landmarks)
    placed: list[dict[str, Any]] = []

    # The instep, so the `foot` row has a height to name. Derived here rather
    # than in the table because it is the one placement whose y is a fraction
    # of another landmark, and a table of names should not carry arithmetic.
    L.setdefault("instep_y", L.get("ankle_y", 0.0) * 0.6)

    # How deep the body is at a given height. A body is not flat: measured on
    # the T-pose figure, its chest centres at +0.023 and its throat at -0.067,
    # so a single torso depth reused for every midline slot put the gorget
    # 0.090 m in front of the neck.
    from operators.gen_3d_object.funcs.code_asset_templates.human_template.figure_fit import (  # noqa: E501
        depth_at,
        leg_x_at,
    )

    for piece in pieces:
        slot = piece["slot"]
        row = SLOTS.get(slot) or (slots or {}).get(slot)
        if row is None:
            known = ", ".join(sorted(set(SLOTS) | set(slots or {})))
            raise ValueError(
                f"{piece['id']}: unknown slot {slot!r}. Known slots: {known}. "
                "An unplaced piece renders inside the figure's ankle, which "
                "reads as a modelling error rather than a spec one."
            )

        side = piece.get("side")
        sign = -1.0 if side == "l" else 1.0

        height = _resolve(row.get("height"), L)
        lateral_spec = row.get("lateral")
        if lateral_spec == "limb":
            # Read at the height the piece actually occupies, for the same
            # reason `midline` is: the limb is not where a single number says.
            lateral = leg_x_at(L, height)
        else:
            lateral = _resolve(lateral_spec, L)
        depth_spec = row.get("depth")
        if depth_spec == "midline":
            depth = depth_at(L, height)
        else:
            depth = _resolve(depth_spec, L)

        at = (sign * lateral if lateral_spec is not None else 0.0,
              height, depth)

        offset = piece.get("offset") or (0.0, 0.0, 0.0)
        at = tuple(at[axis] + offset[axis] for axis in range(3))

        # Into the parent's frame. The resolver adds the parent's translation
        # back on, so this is the inverse of what it will do — stated as one
        # subtraction rather than left as a convention two functions have to
        # agree about silently.
        origin = tuple(float(v) for v in (body_origin or (0.0, 0.0, 0.0)))
        at = tuple(at[axis] - origin[axis] for axis in range(3))

        part: dict[str, Any] = {
            "id": piece["id"],
            "material": piece.get("material", "steel"),
            "at": list(at),
            "rotation": list(piece.get("rotation") or (0.0, 0.0, 0.0)),
            "parent": body_id,
        }

        if piece.get("source"):
            span = float(piece["span"])
            part.update({
                "kind": "mesh",
                "source": piece["source"],
                # Uniform, because a mesh is fitted by one factor: this says
                # "be `span` metres along your longest axis and keep your own
                # proportions". Three numbers would smear the plate.
                "size": [span, span, span],
                "profile": None,
            })
            if piece.get("long_axis"):
                part["long_axis"] = piece["long_axis"]
            if piece.get("trim"):
                part["trim"] = list(piece["trim"])
            # A generated pair usually arrives as one hand — the fetched
            # pauldron leans toward -x, so it is a left shoulder — and the same
            # mesh on both sides puts one set of lames inboard over the ribs.
            # Mirroring the position is not enough, and it is what the chirality
            # gate checks, so the wrong hand passes every gate.
            if piece.get("mirror"):
                part["mirror"] = piece["mirror"]
        else:
            # A stated piece, for the slots where a formula is better than a
            # fetch: a cylinder round a shin is exactly a cylinder.
            part.update({
                "kind": piece.get("kind", "cylinder"),
                "size": list(piece["size"]),
                "segments": piece.get("segments", 16),
            })
            for field in ("profile", "chamfer"):
                if piece.get(field) is not None:
                    part[field] = piece[field]

        placed.append(part)

    return placed


def body_part(source: str, *, part_id: str = "figure", height_metres: float,
              material: str = "skin",
              trim: Sequence[float] | None = None) -> dict[str, Any]:
    """The figure itself, as one `mesh` part standing on the ground.

    ``at`` puts its base at y = 0 rather than its centre at the origin, since
    a figure that floats or sinks is the first thing a reviewer sees and the
    correction is arithmetic nobody should repeat.
    """

    from models.common.glb_writer import load_mesh_asset

    asset = load_mesh_asset(source, trim)
    # The normalised mesh is centred on its own bounds, so half its placed
    # height is exactly how far up its centre goes.
    half = asset["unit_extent"][1] * height_metres / 2.0
    return {
        "id": part_id,
        "kind": "mesh",
        "source": source,
        "size": [height_metres, height_metres, height_metres],
        "at": [0.0, half, 0.0],
        "rotation": [0.0, 0.0, 0.0],
        "material": material,
        "long_axis": "y",
        "profile": None,
        **({"trim": list(trim)} if trim else {}),
    }
