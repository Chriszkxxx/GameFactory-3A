"""Build a 3D asset by evaluating a declarative spec, instead of inferring one.

Image-to-3D is the wrong tool for a class of assets that games are full of.
A crate, a road sign, a rifle, a wheel, a railing: these are exactly
describable, and a reconstruction of one arrives fused, unarticulated,
without a stated size, without a stated facing, and with whatever the
input photograph failed to show invented behind it. ``mesh_cleanup`` and
``orientation_review`` exist to clean up after those failures.

None of them happen here, because nothing is inferred. The spec states
what the object is made of, and the mesh follows from it:

    intent -> spec (JSON) -> evaluate -> vertices -> gates -> GLB

The spec is engine-neutral by construction: it is arithmetic over
primitives, and the output is glTF, which is the one mesh format
:mod:`engine_adapters` accepts on every engine (measured from each
adapter's own importer: UE5 takes ``fbx glb gltf obj usd usda usdz``,
Blender adds ``abc ply usdc``, Unity takes ``fbx glb gltf obj``, three.js
takes ``glb gltf`` — glTF is the intersection).

WHAT THIS BUYS, stated plainly, because "another asset backend" undersells
it. The spec is a few hundred bytes of readable JSON, so unlike a mesh it
can be reviewed in a diff, corrected by editing one number, and regressed
in a unit test. It carries ``units`` and ``forward`` as data, which is the
whole of what ``orientation_review`` is for. Parts keep their names, so a
wheel is still a wheel after export and can be spun by gameplay — the
thing a generated mesh categorically cannot do.

WHERE IT DOES NOT APPLY, equally plainly. Anything organic, anything soft,
anything whose surface is the point: a face, a tree, cloth, a creature.
For those, generation is the right tool and this module should decline —
:func:`suits_code_asset` is that judgement, and ``unsupported`` is a
result, not a failure.

The gates are ported from img2threejs [1], keeping the property that makes
them worth having: each one exists because of a specific measured failure,
and the docstring says which. Three of them are reproduced faithfully
because their failure modes are not three.js specific and will happen here:

    CHIRALITY       img2threejs built a mirrored limb by negating x AND z.
                    Two negations is a 180-degree rotation about Y, and a
                    rotation PRESERVES handedness — so the left hand was
                    the right hand turned around. Measured on the thumb
                    tip: z +0.288 against -0.288, where a mirror leaves z
                    alone. A left/right pair of anything — headlights,
                    wing mirrors, a rifle's sling swivels — is one sign
                    error away from this, and the result looks tidy.

    HOLLOW SHELL    A part with no thickness renders as a shape from the
                    front and disappears edge-on. In img2threejs a bald
                    patch on a scalp survived eight review passes because
                    the silhouette metric could not see it: the defect was
                    interior, and outline agreement is computed from the
                    ~11% of cells that lie on the outline. Geometry gates
                    run on points, before any renderer, so this is caught
                    for free.

    SCALE SANITY    A spec can be internally consistent and still describe
                    a 3 m chair. Nothing downstream can detect it, because
                    a mesh normalised into a unit box has no size of its
                    own — which is why ``art_plan`` carries a height in
                    metres and why that height is checked here against the
                    part extents rather than assumed to agree with them.

The correction loop is bounded for a recorded reason: an unbounded one
spent 45 minutes producing a video of a car that never moved, because a
lookup returned ``None`` and the loop optimised a metric that could not
see it. Repeated defects, oscillation and plateaus all stop the loop, and
``stop_reason`` says which — a loop that gives up loudly costs one message,
a loop that grinds costs a session.

Pure Python 3.10+ standard library. Nothing to install means nothing to
debug in-context, and ``glb_writer`` is stdlib for the same reason.

[1] https://github.com/img2threejs/img2threejs
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

# --------------------------------------------------------------------------
# Spec vocabulary
# --------------------------------------------------------------------------

#: Primitive kinds an evaluator must implement. Deliberately small: this
#: is a hard-surface vocabulary, and every addition is a new way for a
#: spec to be wrong. ``lathe`` and ``extrude`` carry the profile-based
#: shapes (bottles, blades, mouldings) that would otherwise need dozens of
#: bespoke primitives.
PRIMITIVES = ("box", "cylinder", "cone", "sphere", "torus", "lathe", "extrude")

#: Axis names accepted for ``forward``. Written as data because a mesh
#: cannot state which way it faces and every consumer has to be told.
AXES = ("+x", "-x", "+y", "-y", "+z", "-z")

#: The only unit the spec speaks. glTF is metres by definition, and a spec
#: that mixed units would push the conversion into whoever imports it.
UNITS = "metres"

#: Suffixes marking one half of a lateral pair, matching img2threejs [1] so
#: a spec is portable between the two.
LEFT_SUFFIX = "-l"
RIGHT_SUFFIX = "-r"

#: Index of the left-right axis in an ``(x, y, z)`` triple: the only axis a
#: sagittal mirror negates. Named rather than inlined because inlining it
#: is how the recorded rotation bug was written.
LATERAL_AXIS = 0

#: Mirrored coordinates come from negating the same authored number, so
#: they agree to floating-point noise or they disagree structurally.
#: Anything in between is itself a defect worth seeing, which is why this
#: is not a tuning knob.
MIRROR_TOLERANCE = 1e-6

#: Thinner than this, in metres, and a part is a plane pretending to be a
#: solid. Set at a tenth of a millimetre: thinner than any real sheet metal
#: a game would model, thicker than the float noise of a degenerate part.
MIN_PART_THICKNESS = 1e-4

#: A box's ``chamfer`` is a fraction of its half-extent, and at 0.5 the bevel
#: has consumed the face it was cutting back, leaving an octahedron. Kept
#: exclusive so a box always still has six faces.
MAX_CHAMFER = 0.5

#: How close to the axis a lathe profile's end must be to count as capped.
#: A tenth of a millimetre at unit scale: tight enough that a genuinely open
#: tube is caught, loose enough for a radius written as 1e-9 rather than 0.
LATHE_AXIS_TOLERANCE = 1e-4

#: How far the composed height may drift from the declared one before the
#: spec and its stated size have stopped describing the same object. 25%
#: tolerates a pose or a lid left open; beyond it one of the two is wrong.
SCALE_TOLERANCE = 0.25

#: Plausible extents in metres for a role, used only to catch the
#: order-of-magnitude error — a 30 cm door, a 12 m rifle. Wide on purpose:
#: this gate is for the misplaced decimal point, not for art direction.
PLAUSIBLE_HEIGHT_M: dict[str, tuple[float, float]] = {
    "avatar": (0.3, 4.0),
    "weapon": (0.05, 3.0),
    "prop": (0.02, 6.0),
    "scenery": (0.05, 40.0),
    "landmark": (0.5, 200.0),
}

#: Subjects for which a spec is the wrong tool. Matched as substrings, so
#: "oak tree" and "tree_large" both land. Declining is cheap; a
#: procedurally "described" face is not.
ORGANIC_SUBJECTS = (
    "face", "head", "hair", "skin", "creature", "monster", "animal",
    "beast", "tree", "foliage", "leaf", "plant", "flower", "grass",
    "cloth", "fabric", "drape", "flag", "hand", "character", "person",
    "human", "figure", "body", "muscle", "organic", "rock", "terrain",
)

#: Subjects a spec handles well. Also substrings. The material and
#: mechanism words at the end are what tip a borderline subject: a "stone
#: golem" is a stack of blocks, and without them a single organic word
#: decided it unopposed.
HARD_SURFACE_SUBJECTS = (
    "crate", "box", "barrel", "chest", "container", "crateboard",
    "sign", "signpost", "post", "pole", "fence", "railing", "rail",
    "wheel", "gear", "cog", "pipe", "tube", "beam", "girder",
    "sword", "blade", "knife", "axe", "hammer", "rifle", "pistol",
    "gun", "weapon", "shield", "helmet", "armour", "armor",
    "table", "chair", "bench", "desk", "shelf", "door", "window",
    "lamp", "lantern", "torch", "crystal", "gem", "coin", "key",
    "wall", "pillar", "column", "arch", "stair", "platform", "ramp",
    "vehicle", "car", "cart", "wagon", "turret", "antenna", "drone",
    "stone", "metal", "steel", "iron", "wood", "plank", "brick",
    "golem", "robot", "mech", "construct", "statue", "machine",
)


class SpecError(ValueError):
    """The spec cannot be evaluated. Distinct from a gate failure: a gate
    failure is a judgement about a mesh that exists, this is a spec that
    does not describe one."""


# --------------------------------------------------------------------------
# Routing: is a spec the right tool at all?
# --------------------------------------------------------------------------


def suits_code_asset(
    subject: str,
    *,
    asset_type: str = "prop",
) -> dict[str, Any]:
    """Whether ``subject`` should be built from a spec or generated.

    Returns ``{"suitable", "confidence", "reason", "route"}`` where
    ``route`` is ``"code"``, ``"generate"`` or ``"ambiguous"``.

    Declining is the point. img2threejs [1] reports ``unsupported-family``
    rather than attempting a subject outside its range, and its own README
    concedes that characters come out as stylised reconstructions rather
    than likenesses. A spec that cannot describe a face should say so in
    one call instead of spending a correction loop discovering it.

    ``ambiguous`` is returned rather than guessed for a subject that reads
    both ways — a "stone golem" is hard-surface in silhouette and organic
    in surface — because the caller knows which of the two matters for the
    shot the asset appears in.
    """

    text = f"{subject} {asset_type}".lower()
    organic = [word for word in ORGANIC_SUBJECTS if word in text]
    hard = [word for word in HARD_SURFACE_SUBJECTS if word in text]

    # Judged on the balance of evidence, not on whether any organic word is
    # present. Counting a single match as a veto made "stone golem creature"
    # route to generation on the strength of one word against two, and the
    # same logic would have sent a "rock crusher machine" the same way. A
    # decisive majority routes; anything near parity is ambiguous, which is
    # the honest answer for a subject that genuinely reads both ways.
    if organic and hard and abs(len(organic) - len(hard)) < 2:
        return {
            "suitable": False,
            "confidence": 0.5,
            "route": "ambiguous",
            "reason": (
                f"{subject!r} reads both ways — hard-surface "
                f"({', '.join(hard)}) and organic ({', '.join(organic)}). "
                "Decide from the shot: a spec if the silhouette carries it, "
                "generation if the surface does."
            ),
        }

    if organic and len(organic) > len(hard):
        return {
            "suitable": False,
            "confidence": 0.9,
            "route": "generate",
            "reason": (
                f"{subject!r} reads as organic ({', '.join(organic)}). A "
                "spec describes arithmetic over primitives, which is the "
                "wrong tool for a surface that is the point of the asset — "
                "use image-to-3D and review the mesh."
            ),
        }
    if hard and len(hard) > len(organic):
        return {
            "suitable": True,
            "confidence": 0.9 if not organic else 0.7,
            "route": "code",
            "reason": (
                f"{subject!r} reads as hard-surface ({', '.join(hard)}): "
                "exactly describable, so a spec gives a named-part mesh "
                "with a stated size and facing."
            ),
        }
    return {
        "suitable": False,
        "confidence": 0.3,
        "route": "ambiguous",
        "reason": (
            f"{subject!r} matches no known family. Prefer a spec when the "
            "object can be written down as boxes and cylinders, and "
            "generation when it cannot."
        ),
    }


# --------------------------------------------------------------------------
# Spec validation
# --------------------------------------------------------------------------


def _as_vec3(value: Any, field: str, default: tuple[float, float, float]
             ) -> tuple[float, float, float]:
    if value is None:
        return default
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise SpecError(f"{field} must be three numbers, got {value!r}")
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError) as exc:
        raise SpecError(f"{field} must be three numbers: {exc}") from exc


def _as_chamfer(value: Any, part_id: str) -> float:
    """Validate a box's edge cut-back, a fraction of the half-extent.

    Rejected rather than clamped when out of range. A chamfer of 0.5 has
    eaten the whole half-extent and the face it was cutting back no longer
    exists — the box has become an octahedron. Silently clamping would hand
    back a shape nobody asked for and let the spec keep claiming it is a box.
    """

    if value is None:
        return 0.0
    try:
        chamfer = float(value)
    except (TypeError, ValueError) as exc:
        raise SpecError(f"{part_id}.chamfer must be a number: {exc}") from exc
    if not 0.0 <= chamfer < MAX_CHAMFER:
        raise SpecError(
            f"{part_id}.chamfer must be in [0, {MAX_CHAMFER}), got {chamfer}. "
            "It is a fraction of the half-extent, so 0.5 consumes the face "
            "it was bevelling and leaves an octahedron, not a box."
        )
    return chamfer


def _as_profile(value: Any, part_id: str, kind: str
                ) -> tuple[tuple[float, float], ...] | None:
    """Validate a lathe or extrude profile, or return None for other kinds.

    The two kinds have genuinely different requirements, and conflating them
    is what makes a turned part hard to author:

    A lathe revolves ``(radius, height)`` about the local Y axis. It only
    encloses a volume if the profile *starts and ends on the axis*, radius
    zero. Otherwise the revolved surface is a pipe with two open ends — no
    interior, nothing watertight, and the inside visible through the hole.
    This is the easiest mistake in the vocabulary to make, because a list of
    radii down the length of a barrel reads as completely sensible and the
    defect is invisible until something is behind it. A negative radius is
    likewise refused: it revolves through the axis and self-intersects.

    An extrude pushes a closed ``(x, y)`` outline along Z and caps both ends,
    so it needs three points to bound an area but has no axis to touch.

    Refused here rather than reported by a gate because, unlike a proportion
    or a placement, there is no version of an unclosed lathe that was
    intended — there is nothing for a correction loop to weigh.
    """

    if kind not in ("lathe", "extrude"):
        return value if value is None else tuple(
            (float(a), float(b)) for a, b in value
        )

    if not isinstance(value, (list, tuple)) or not value:
        raise SpecError(
            f"{part_id}: a {kind} needs a `profile`; without one there is no "
            "shape to revolve or push, only a size"
        )

    points: list[tuple[float, float]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise SpecError(
                f"{part_id}.profile[{index}] must be two numbers, got {entry!r}"
            )
        try:
            points.append((float(entry[0]), float(entry[1])))
        except (TypeError, ValueError) as exc:
            raise SpecError(f"{part_id}.profile[{index}]: {exc}") from exc

    minimum = 2 if kind == "lathe" else 3
    if len(points) < minimum:
        raise SpecError(
            f"{part_id}.profile needs at least {minimum} points for a {kind}, "
            f"got {len(points)}"
        )

    if kind == "extrude":
        return tuple(points)

    negative = [
        f"[{index}]={radius}"
        for index, (radius, _height) in enumerate(points)
        if radius < 0.0
    ]
    if negative:
        raise SpecError(
            f"{part_id}.profile has a negative radius at {', '.join(negative)}. "
            "A lathe profile is (radius, height) and a negative radius sweeps "
            "back through the axis, so the surface intersects itself."
        )

    open_ends = [
        name
        for name, radius in (("first", points[0][0]), ("last", points[-1][0]))
        if radius > LATHE_AXIS_TOLERANCE
    ]
    if open_ends:
        raise SpecError(
            f"{part_id}.profile does not close on the axis: its "
            f"{' and '.join(open_ends)} point(s) have a non-zero radius "
            f"({points[0][0]}, {points[-1][0]}). A revolved profile only "
            "encloses a volume if it begins and ends at radius 0; otherwise "
            "it is a pipe with two open ends, which has no interior and shows "
            "it once anything is behind it. Add (0.0, "
            f"{points[0][1]}) and (0.0, {points[-1][1]}) to cap it."
        )

    return tuple(points)


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Check a spec is evaluable, and normalise it.

    Raises :class:`SpecError` on anything that would make the mesh
    meaningless rather than merely ugly: a missing subject, no parts, an
    unknown primitive, a part with a non-positive dimension, a duplicate
    part id.

    ``units`` and ``forward`` are required with no default. A default here
    would be the same silent-wrong-answer that ``orientation_review``
    exists to catch: a mesh whose facing was assumed reads as correct
    until it is in a scene walking backwards.
    """

    if not isinstance(spec, dict):
        raise SpecError(f"a spec must be a dict, got {type(spec).__name__}")

    subject = str(spec.get("subject") or "").strip()
    if not subject:
        raise SpecError("spec.subject is required: it is what the gates report against")

    units = str(spec.get("units") or "").strip().lower()
    if units != UNITS:
        raise SpecError(
            f"spec.units must be {UNITS!r} (glTF is metres by definition); got {units!r}"
        )

    forward = str(spec.get("forward") or "").strip().lower()
    if forward not in AXES:
        raise SpecError(
            f"spec.forward must be one of {AXES}; got {forward!r}. It is "
            "required because a mesh cannot state which way it faces, and "
            "an assumed facing is the defect orientation_review exists for."
        )

    raw_parts = spec.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise SpecError("spec.parts must be a non-empty list")

    parts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_parts):
        if not isinstance(raw, dict):
            raise SpecError(f"parts[{index}] must be a dict, got {type(raw).__name__}")
        part_id = str(raw.get("id") or "").strip()
        if not part_id:
            raise SpecError(
                f"parts[{index}].id is required: named parts are what lets "
                "gameplay drive a wheel after export"
            )
        if part_id in seen:
            raise SpecError(f"duplicate part id {part_id!r}")
        seen.add(part_id)

        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in PRIMITIVES:
            raise SpecError(
                f"{part_id}: unknown kind {kind!r}; expected one of {PRIMITIVES}"
            )

        size = _as_vec3(raw.get("size"), f"{part_id}.size", (1.0, 1.0, 1.0))
        if any(value <= 0 for value in size):
            raise SpecError(
                f"{part_id}.size must be positive in every axis, got {size}. "
                "A zero extent is a plane pretending to be a solid, and it "
                "vanishes when seen edge-on."
            )

        parts.append({
            "id": part_id,
            "kind": kind,
            "size": size,
            "at": _as_vec3(raw.get("at"), f"{part_id}.at", (0.0, 0.0, 0.0)),
            "rotation": _as_vec3(
                raw.get("rotation"), f"{part_id}.rotation", (0.0, 0.0, 0.0)
            ),
            "material": str(raw.get("material") or "default"),
            "profile": _as_profile(raw.get("profile"), part_id, kind),
            "segments": int(raw.get("segments") or 16),
            "chamfer": _as_chamfer(raw.get("chamfer"), part_id),
        })

    return {
        "subject": subject,
        "units": units,
        "forward": forward,
        "asset_type": str(spec.get("asset_type") or "prop"),
        "height_metres": (
            float(spec["height_metres"])
            if spec.get("height_metres") is not None
            else None
        ),
        "parts": parts,
        "materials": dict(spec.get("materials") or {}),
        "notes": str(spec.get("notes") or ""),
    }


# --------------------------------------------------------------------------
# Geometry, derived from the spec without a renderer
# --------------------------------------------------------------------------


def part_bounds(part: dict[str, Any]) -> tuple[tuple[float, float, float],
                                               tuple[float, float, float]]:
    """Axis-aligned ``(low, high)`` of one part, in metres.

    Delegates to the writer's :func:`~models.common.glb_writer.rotated_bounds`
    rather than resolving the rotation here. That is not tidiness: a first
    draft of this function swapped extents for right-angle rotations, which
    is exact at 90 degrees and silently wrong at 30, so the gates would have
    been measuring a different object from the one being written. One
    implementation cannot disagree with itself.
    """

    from models.common.glb_writer import rotated_bounds

    return rotated_bounds(
        part["size"], part["at"], part["rotation"],
        profile=part.get("profile"), kind=part["kind"],
    )


def spec_bounds(spec: dict[str, Any]) -> dict[str, Any]:
    """Composed bounds of every part: ``low``, ``high``, ``extents``, ``centre``."""

    lows: list[tuple[float, float, float]] = []
    highs: list[tuple[float, float, float]] = []
    for part in spec["parts"]:
        low, high = part_bounds(part)
        lows.append(low)
        highs.append(high)

    low = tuple(min(value[axis] for value in lows) for axis in range(3))
    high = tuple(max(value[axis] for value in highs) for axis in range(3))
    return {
        "low": [round(value, 6) for value in low],
        "high": [round(value, 6) for value in high],
        "extents": [round(high[axis] - low[axis], 6) for axis in range(3)],
        "centre": [round((low[axis] + high[axis]) / 2.0, 6) for axis in range(3)],
    }


def estimate_triangles(spec: dict[str, Any]) -> int:
    """Triangle count the spec will evaluate to.

    Available before anything is built, which is the point: a triangle
    budget cannot be fixed after the fact — decimating a textured mesh
    outside its generator throws the UVs away — so a spec that would blow
    the budget should be edited, not decimated.

    These formulas mirror the writer's tessellation exactly, and the test
    asserts the two agree. A first draft used ``segments ** 2`` for the
    round primitives where the writer rings them at ``segments // 2``,
    which over-counted by 2x and would have failed the budget gate on
    meshes that were inside it — a gate that rejects good work gets
    switched off, and then it protects nothing.
    """

    total = 0
    for part in spec["parts"]:
        segments = max(3, int(part["segments"]))
        rings = max(3, segments // 2)
        kind = part["kind"]
        if kind == "box":
            # 6 shrunken faces + 12 edge bevels, two triangles each, plus one
            # per corner. A chamfered box is not free: it costs 44 against 12,
            # which is exactly why the budget gate has to know about it.
            total += 44 if part.get("chamfer") else 12
        elif kind == "cylinder":
            total += segments * 4          # wall (2) + two caps (1 each)
        elif kind == "cone":
            total += segments * 2          # slant + base
        elif kind in ("sphere", "torus"):
            total += segments * rings * 2
        elif kind == "lathe":
            points = len(part.get("profile") or ()) or 2
            total += max(1, points - 1) * segments * 2
        elif kind == "extrude":
            points = len(part.get("profile") or ()) or 4
            total += points * 2 + max(0, points - 2) * 2   # walls + two caps
    return total


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------


def _mirror(point: Sequence[float]) -> tuple[float, float, float]:
    """The sagittal mirror of a position: negate the lateral axis only.

    Its own function because the reflex is to think a direction transforms
    differently, and reaching for a rotation here is precisely the recorded
    bug.
    """

    values = [float(value) for value in point]
    values[LATERAL_AXIS] = -values[LATERAL_AXIS]
    return (values[0], values[1], values[2])


def _pair_stem(part_id: str) -> tuple[str, str] | None:
    for suffix, side in ((LEFT_SUFFIX, "l"), (RIGHT_SUFFIX, "r")):
        if part_id.endswith(suffix):
            return part_id[: -len(suffix)], side
    return None


def check_chirality(spec: dict[str, Any]) -> dict[str, Any]:
    """Every ``-l``/``-r`` pair must be a reflection, not a rotation.

    THE RECORDED FAILURE. img2threejs [1] placed a mirrored limb as
    ``[side*along, height, side*across]``, negating x AND z. Two negations
    is a 180-degree rotation about Y, and a rotation preserves handedness,
    so the left hand was the right hand turned around. Measured on the
    thumb tip: z +0.288 on one side against -0.288 on the other, where a
    mirror leaves z untouched.

    It is reported as ``rotation`` rather than as a generic mismatch
    because the two are trivially confused: they agree exactly for any part
    sitting on the midline, which is why a symmetric body never exposes it
    and a pair of headlights does.
    """

    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for part in spec["parts"]:
        parsed = _pair_stem(part["id"])
        if parsed:
            stem, side = parsed
            pairs.setdefault(stem, {})[side] = part

    failures: list[str] = []
    checked = 0
    for stem, sides in sorted(pairs.items()):
        if "l" not in sides or "r" not in sides:
            failures.append(
                f"{stem}: only the {'left' if 'l' in sides else 'right'} half "
                "is present. A lateral pair with one half missing is a "
                "modelling omission, not a style choice."
            )
            continue
        checked += 1
        right = sides["r"]["at"]
        left = sides["l"]["at"]
        expected = _mirror(right)

        def close(a: Sequence[float], b: Sequence[float]) -> bool:
            return all(abs(x - y) <= MIRROR_TOLERANCE for x, y in zip(a, b))

        if close(expected, left):
            if sides["r"]["size"] != sides["l"]["size"]:
                failures.append(
                    f"{stem}: the halves are mirrored in position but differ "
                    f"in size ({sides['r']['size']} against "
                    f"{sides['l']['size']})."
                )
            continue
        if close((-right[0], right[1], -right[2]), left):
            failures.append(
                f"{stem}: the left half is the right half ROTATED about the "
                f"vertical axis, not mirrored. A rotation preserves "
                f"handedness, so both halves are the same hand. right "
                f"{tuple(round(v, 6) for v in right)} should mirror to "
                f"{tuple(round(v, 6) for v in expected)}, but the left is "
                f"{tuple(round(v, 6) for v in left)}. Negate the lateral "
                f"axis only."
            )
        elif close(right, left):
            failures.append(
                f"{stem}: both halves sit at the same place — the left is the "
                f"right translated, not mirrored at all. Expected "
                f"{tuple(round(v, 6) for v in expected)}."
            )
        else:
            failures.append(
                f"{stem}: the halves are not a sagittal mirror. right "
                f"{tuple(round(v, 6) for v in right)} mirrors to "
                f"{tuple(round(v, 6) for v in expected)}, but the left is "
                f"{tuple(round(v, 6) for v in left)}."
            )

    return {
        "gate": "chirality",
        "ok": not failures,
        "pairs_checked": checked,
        "failures": failures,
    }


def check_solidity(spec: dict[str, Any]) -> dict[str, Any]:
    """No part may be thin enough to vanish edge-on.

    A part with an extent at floating-point zero renders as a shape from
    the front and disappears from the side. This is the class of defect
    img2threejs [1] recorded as surviving eight review passes: the bald
    patch was *interior*, and silhouette agreement is computed from the
    ~11% of cells lying on the outline, so an outline metric could not see
    it. Points can, and points are available before any renderer is
    started — which is the whole argument for gating geometry first.
    """

    failures: list[str] = []
    for part in spec["parts"]:
        thinnest = min(part["size"])
        if thinnest < MIN_PART_THICKNESS:
            axis = "xyz"[part["size"].index(thinnest)]
            failures.append(
                f"{part['id']}: {thinnest:.2e} m thick on {axis} — below "
                f"{MIN_PART_THICKNESS:.0e} m this is a plane pretending to "
                "be a solid and disappears when seen edge-on. Give it real "
                "thickness or model it as a decal."
            )
    return {"gate": "solidity", "ok": not failures, "failures": failures}


def check_scale(spec: dict[str, Any]) -> dict[str, Any]:
    """The composed mesh must be the size the spec says it is.

    Two different mistakes, and only the first is usually looked for.

    A misplaced decimal point gives a 30 cm door: caught against
    :data:`PLAUSIBLE_HEIGHT_M`, which is deliberately wide because this
    gate is for orders of magnitude, not for art direction.

    Worse is a spec whose ``height_metres`` and whose parts disagree.
    Nothing downstream can detect that, because a mesh normalised into a
    unit box has no size of its own — the declared height is the only
    record of how big the thing is, and if the parts say otherwise then one
    of the two is a lie. A chair at 3 m and a doorway at 1.6 m are what
    make a scene read as a toy.
    """

    bounds = spec_bounds(spec)
    height = bounds["extents"][1]
    declared = spec.get("height_metres")
    role = spec.get("asset_type") or "prop"

    failures: list[str] = []
    warnings: list[str] = []

    low, high = PLAUSIBLE_HEIGHT_M.get(role, PLAUSIBLE_HEIGHT_M["prop"])
    if not (low <= height <= high):
        failures.append(
            f"composed height {height:.3f} m is outside the plausible range "
            f"for a {role} ({low}–{high} m). This range is wide on purpose: "
            "being outside it means a decimal point, not a style."
        )

    if declared is not None:
        if declared <= 0:
            failures.append(f"height_metres must be positive, got {declared}")
        elif height > 0:
            drift = abs(height - declared) / declared
            if drift > SCALE_TOLERANCE:
                failures.append(
                    f"the parts compose to {height:.3f} m but the spec "
                    f"declares {declared:.3f} m ({drift:.0%} apart). The "
                    "declared height is the only record of how big this is "
                    "once the mesh is normalised, so one of the two is "
                    "wrong — fix the parts or fix the declaration."
                )
            elif drift > SCALE_TOLERANCE / 2:
                warnings.append(
                    f"composed height {height:.3f} m against a declared "
                    f"{declared:.3f} m ({drift:.0%})"
                )

    return {
        "gate": "scale",
        "ok": not failures,
        "height_metres": height,
        "declared_metres": declared,
        "bounds": bounds,
        "failures": failures,
        "warnings": warnings,
    }


def check_budget(spec: dict[str, Any], *, limit: int | None = None) -> dict[str, Any]:
    """The spec must evaluate inside its role's triangle budget.

    Checked on the spec rather than on the mesh because that is the only
    point at which it can still be fixed cheaply: a budget overrun is
    repaired by lowering ``segments``, and decimating afterwards throws the
    UVs away. Budgets come from ``art_plan.BUDGET_BY_ROLE`` — keyed by role
    rather than asset type, because what costs frame time is how *often* a
    thing is drawn.
    """

    if limit is None:
        try:
            from .art_plan import BUDGET_BY_ROLE
        except ImportError:  # standalone use
            BUDGET_BY_ROLE = {"prop": (20_000, 1024)}
        role = spec.get("asset_type") or "prop"
        limit = BUDGET_BY_ROLE.get(role, BUDGET_BY_ROLE["prop"])[0]

    triangles = estimate_triangles(spec)
    over = triangles > limit
    return {
        "gate": "budget",
        "ok": not over,
        "triangles": triangles,
        "limit": limit,
        "failures": (
            [
                f"the spec evaluates to {triangles} triangles against a "
                f"budget of {limit}. Lower `segments` on the round parts: "
                "a triangle budget cannot be fixed after export, because "
                "decimating a textured mesh outside its generator discards "
                "the UVs."
            ]
            if over
            else []
        ),
    }


def check_connectivity(spec: dict[str, Any]) -> dict[str, Any]:
    """Report parts that touch nothing else.

    Reported, never failed. A floating part is usually a mistake — a wheel
    placed off its axle, a handle beside its door — but it is legitimately
    a design: a hovering crystal, an orbiting ring, a muzzle flash socket.
    Failing this would make the gate wrong for a whole class of asset,
    while reporting it costs one line in the review and catches the wheel.
    """

    parts = spec["parts"]
    boxes = [part_bounds(part) for part in parts]
    isolated: list[str] = []
    for index, part in enumerate(parts):
        if len(parts) == 1:
            break
        low_a, high_a = boxes[index]
        touching = False
        for other in range(len(parts)):
            if other == index:
                continue
            low_b, high_b = boxes[other]
            gap = max(
                max(low_a[axis] - high_b[axis], low_b[axis] - high_a[axis])
                for axis in range(3)
            )
            if gap <= MIN_PART_THICKNESS:
                touching = True
                break
        if not touching:
            isolated.append(part["id"])

    return {
        "gate": "connectivity",
        "ok": True,
        "isolated_parts": isolated,
        "warnings": (
            [
                f"{len(isolated)} part(s) touch nothing else "
                f"({', '.join(isolated)}). Intentional for a hovering or "
                "orbiting element; otherwise a misplaced part."
            ]
            if isolated
            else []
        ),
    }


#: Gates run in ascending cost order, which is also the order in which a
#: failure invalidates the ones after it: an unevaluable spec has no
#: bounds, and bounds are what the scale gate reads.
def check_windings(spec: dict[str, Any]) -> dict[str, Any]:
    """Every part must be a closed solid whose faces point outward.

    The one gate here that evaluates the mesh rather than the spec, and the
    one that had to be added after the fact. Four of the seven primitives
    shipped inside-out: their quads were wound (a, b, b+1) where outward is
    (a, b+1, b), so a unit cylinder enclosed -0.26 where the true volume is
    +0.785. Nothing noticed. The GLB was valid, triangle counts matched,
    bounds were right, all five other gates passed, and the defect is
    invisible in any viewer that does not cull backfaces — so it would have
    surfaced first inside an engine, on the far side of the handoff.

    That is the argument for spending the evaluation here. The other gates
    check the spec's *intent*: proportions, placement, declared size. This
    one checks that the evaluation of that intent is a solid at all, which no
    amount of reading the spec can establish.

    Two measures per part:

    * signed volume, from the divergence theorem over the triangles. Positive
      means outward. Checking the magnitude too, not just the sign, is what
      catches a part wound correctly on its walls and backwards on its caps,
      where the two partly cancel.
    * boundary edges: any edge used by one triangle rather than two is a hole,
      and a surface with a hole has no well-defined inside to be outside of.

    Failed rather than warned. Unlike a floating part there is no asset for
    which an inverted solid is the intent.
    """

    from models.common.glb_writer import build_part

    failures: list[str] = []
    inverted: list[str] = []
    open_parts: list[str] = []

    for part in spec["parts"]:
        positions, _normals, indices = build_part(part)

        volume = 0.0
        edges: dict[frozenset, int] = {}
        for triangle in range(len(indices) // 3):
            a, b, c = [positions[indices[triangle * 3 + k]] for k in range(3)]
            volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
            keys = [tuple(round(value, 7) for value in point) for point in (a, b, c)]
            for first, second in ((0, 1), (1, 2), (2, 0)):
                edge = frozenset((keys[first], keys[second]))
                edges[edge] = edges.get(edge, 0) + 1

        boundary = sum(1 for count in edges.values() if count == 1)
        if boundary:
            open_parts.append(f"{part['id']} ({boundary} boundary edge(s))")
        if volume <= 0.0:
            inverted.append(f"{part['id']} ({volume:+.6g})")

    if inverted:
        failures.append(
            f"{len(inverted)} part(s) are inside-out, enclosing a negative "
            f"volume: {', '.join(inverted)}. Their faces point inward, so "
            "they will be invisible or hollow in any engine that culls "
            "backfaces — and identical to a correct solid in a viewer that "
            "does not, which is why this is checked here and not by eye."
        )
    if open_parts:
        failures.append(
            f"{len(open_parts)} part(s) are not closed: {', '.join(open_parts)}. "
            "An edge belonging to one triangle instead of two is a hole. For a "
            "lathe this usually means the profile does not return to radius 0 "
            "at both ends, leaving a tube with open ends."
        )

    return {
        "gate": "windings",
        "ok": not failures,
        "parts_checked": len(spec["parts"]),
        "inverted": inverted,
        "unclosed": open_parts,
        "failures": failures,
    }


GATES: tuple[Callable[[dict[str, Any]], dict[str, Any]], ...] = (
    check_solidity,
    check_chirality,
    check_scale,
    check_budget,
    check_connectivity,
    # Last: the only gate that evaluates the mesh, so the only one whose cost
    # scales with the triangle count rather than the part count.
    check_windings,
)


def run_gates(spec: dict[str, Any]) -> dict[str, Any]:
    """Run every gate. Returns ``{"ok", "reports", "failures", "warnings"}``.

    Every gate runs even after one fails, because the correction loop needs
    the whole defect list: fixing one defect per iteration is how a bounded
    loop is exhausted by a spec with three of them.
    """

    reports = [gate(spec) for gate in GATES]
    failures = [
        message for report in reports for message in report.get("failures", ())
    ]
    warnings = [
        message for report in reports for message in report.get("warnings", ())
    ]
    return {
        "ok": not failures,
        "reports": reports,
        "failures": failures,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------
# Bounded correction loop
# --------------------------------------------------------------------------

#: Attempts before giving up. Three, matching img2threejs [1], and for its
#: reason: a defect that survives three targeted corrections is not being
#: understood, and a fourth attempt is the same attempt.
MAX_ATTEMPTS = 3


def correct_spec(
    spec: dict[str, Any],
    revise: Callable[[dict[str, Any], list[str]], dict[str, Any]],
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Gate, revise, re-gate — with a hard stop and a stated reason.

    ``revise(spec, failures) -> spec`` is where the model edits the spec.

    THE FAILURE THIS IS SHAPED BY. An unbounded loop in img2threejs [1]
    spent 45 minutes recording a car that never moved: a lookup returned
    ``None``, the loop optimised a metric that could not see it, and
    nothing raised. So this stops on all four ways a loop fails to
    converge, and ``stop_reason`` distinguishes them:

        ``passed``      every gate is green.
        ``exhausted``   the attempt budget ran out.
        ``repeating``   the identical defect set came back. Nothing was
                        fixed, so another attempt cannot help.
        ``oscillating`` a defect set seen two attempts ago is back. The
                        revisions are trading one defect for another.
        ``no_progress`` the count did not fall. Distinct from
                        ``repeating``: different defects, no fewer of them.
        ``revise_failed`` the reviser raised. Reported, not swallowed —
                        a reviser that cannot produce a spec is the loud
                        version of the silent early return.
    """

    history: list[tuple[str, ...]] = []
    current = spec
    attempts = 0
    best: dict[str, Any] = {**run_gates(current), "spec": current}

    def stop(reason: str, detail: str = "") -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": False,
            "spec": best["spec"],
            "attempts": attempts,
            "stop_reason": reason,
            "gates": best,
        }
        if detail:
            out["detail"] = detail
        return out

    while True:
        result = run_gates(current)
        fingerprint = tuple(sorted(result["failures"]))
        if len(result["failures"]) < len(best["failures"]):
            best = {**result, "spec": current}

        if result["ok"]:
            return {
                "ok": True,
                "spec": current,
                "attempts": attempts,
                "stop_reason": "passed",
                "gates": result,
            }

        # Three ways a loop fails to converge, kept apart because the
        # response to each differs: revise harder, revise differently, or
        # stop and report that the spec is wrong. Only checked once there is
        # a previous attempt to compare against — judging the first pass
        # against nothing is how a loop stops before it starts.
        if history:
            if fingerprint == history[-1]:
                return stop(
                    "repeating",
                    "the identical defect set came back, so the last "
                    "revision addressed none of it",
                )
            if fingerprint in history:
                return stop(
                    "oscillating",
                    "a defect set from an earlier attempt has returned: "
                    "defects are being traded for one another",
                )
            if len(fingerprint) >= len(history[-1]):
                return stop(
                    "no_progress",
                    f"{len(fingerprint)} defect(s) after attempt {attempts}, "
                    f"no fewer than the {len(history[-1])} before it",
                )

        history.append(fingerprint)

        if attempts >= max_attempts:
            return stop(
                "exhausted",
                f"{len(best['failures'])} defect(s) left after "
                f"{max_attempts} attempt(s)",
            )

        attempts += 1
        try:
            current = validate_spec(revise(current, list(result["failures"])))
        except Exception as exc:  # noqa: BLE001 — reported, never swallowed
            return stop("revise_failed", f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def build_code_asset(
    spec: dict[str, Any],
    out_path: str,
    *,
    revise: Callable[[dict[str, Any], list[str]], dict[str, Any]] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Validate, gate and write a spec as a GLB.

    Returns a report carrying ``ok``, ``glb_path``, ``spec``, ``gates``,
    ``triangles``, ``bounds``, ``forward_axis``, ``scale_hint_metres`` and
    ``warnings``.

    ``forward_axis`` and ``scale_hint_metres`` come straight out of the
    spec rather than being inferred from the mesh, which is the practical
    payoff of this route: ``asset_import`` requires both, and for a
    generated mesh they can only be guessed from the input view — a guess
    that gets recorded as ``heuristic`` precisely so that nobody mistakes
    it for a fact.

    ``strict`` refuses to write a mesh that failed a gate. Left on by
    default: a wrong asset that exists gets used.
    """

    validated = validate_spec(spec)

    if revise is not None:
        outcome = correct_spec(validated, revise)
    else:
        gates_once = run_gates(validated)
        outcome = {
            "ok": gates_once["ok"],
            "spec": validated,
            "attempts": 0,
            "stop_reason": "passed" if gates_once["ok"] else "not_attempted",
            "gates": gates_once,
        }
    final = outcome["spec"]
    gates = outcome["gates"]

    report: dict[str, Any] = {
        "ok": bool(outcome["ok"]),
        "glb_path": None,
        "spec": final,
        "subject": final["subject"],
        "gates": gates,
        "attempts": outcome["attempts"],
        "stop_reason": outcome["stop_reason"],
        "triangles": estimate_triangles(final),
        "bounds": spec_bounds(final),
        "forward_axis": final["forward"],
        "scale_hint_metres": final.get("height_metres"),
        "part_ids": [part["id"] for part in final["parts"]],
        "warnings": list(gates.get("warnings", ())),
        "failures": list(gates.get("failures", ())),
    }
    if outcome.get("detail"):
        report["detail"] = outcome["detail"]

    if not report["ok"] and strict:
        report["warnings"].append(
            f"nothing was written: {len(report['failures'])} gate failure(s), "
            f"stopped as {report['stop_reason']}. Pass strict=False to "
            "inspect the mesh anyway."
        )
        return report

    from models.common.glb_writer import write_spec_glb

    report["glb_path"] = write_spec_glb(final, out_path)
    return report
