#!/usr/bin/env python3
"""
test/test_3d_object_spec.py

Prove the spec route to a 3D object builds the mesh it claims to, and refuses
the ones it should.

Run:

    python test/test_3d_object_spec.py

Companion to `test_3d_object_gen.py`, which covers the generated route. No
dependencies, no network, no GPU, no model — which is the point. This is the
one 3D asset path that can be regression-tested at all: a generated mesh is
one sample of a model's behaviour and cannot be varied, so `test_3d_object_gen`
can only check that a file appeared. A spec is data, so the mesh that follows
from it is deterministic and every gate has a case that must fail.

Two classes of check here, and the second is the one that matters.

    THE GATES CATCH WHAT THEY WERE WRITTEN FOR. Each case reproduces a defect
    recorded in img2threejs [1] — the rotation-instead-of-mirror, the
    zero-thickness part, the declared size that disagrees with the parts. A
    gate whose failing case is not pinned down decays into decoration.

    THE GATES DO NOT CATCH ANYTHING ELSE. The risk with a gate is not a missed
    defect, which shows up in the review sheet — it is a false positive that
    blocks a legitimate asset, because that trains whoever hits it to pass
    `strict=False` and then no gate means anything. So a true mirror, a
    deliberately hovering part, and a spec at the budget limit all have to
    pass.

[1] https://github.com/img2threejs/img2threejs
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  ok   {name}")
        return
    FAILED.append(f"{name}: {detail}")
    print(f"  FAIL {name} {detail}")


def spec(parts: list[dict], **overrides) -> dict:
    """A minimal valid spec with `parts` swapped in."""
    base = {
        "subject": "test rig",
        "units": "metres",
        "forward": "+z",
        "asset_type": "prop",
        "height_metres": 1.0,
    }
    base.update(overrides)
    base["parts"] = parts
    return base


def failed_gates(candidate: dict) -> list[str]:
    from operators.gen_3d_object.funcs.code_asset import run_gates, validate_spec

    return run_gates(validate_spec(candidate))["failures"]


# --------------------------------------------------------------------------


def test_validation() -> None:
    print("\nspec validation")
    from operators.gen_3d_object.funcs.code_asset import SpecError, validate_spec

    def rejects(name: str, candidate: dict, expect: str) -> None:
        try:
            validate_spec(candidate)
        except SpecError as exc:
            check(name, expect in str(exc), f"wrong reason: {exc}")
        else:
            check(name, False, "accepted a spec it should have rejected")

    body = [{"id": "b", "kind": "box", "size": [0.5, 1.0, 0.5], "at": [0, 0.5, 0]}]

    # Facing and units have no defaults on purpose: an assumed facing is the
    # defect `orientation_review` exists to catch, and it looks correct until
    # the asset is in a scene walking backwards.
    missing_forward = spec(body)
    del missing_forward["forward"]
    rejects("a missing facing is refused", missing_forward, "spec.forward")

    bad_axis = spec(body, forward="north")
    rejects("an unknown axis is refused", bad_axis, "spec.forward")

    rejects("non-metre units are refused", spec(body, units="cm"), "spec.units")
    rejects("an empty part list is refused", spec([]), "non-empty")
    rejects(
        "a duplicate part id is refused",
        spec(body + [{"id": "b", "kind": "box", "size": [1, 1, 1]}]),
        "duplicate part id",
    )
    rejects(
        "an unknown primitive is refused",
        spec([{"id": "x", "kind": "nurbs", "size": [1, 1, 1]}]),
        "unknown kind",
    )
    rejects(
        "a zero dimension is refused",
        spec([{"id": "x", "kind": "box", "size": [1, 0, 1]}]),
        "positive",
    )
    rejects("a spec with no subject is refused", spec(body, subject=""), "subject")

    valid = validate_spec(spec(body))
    check("a valid spec normalises", valid["forward"] == "+z" and len(valid["parts"]) == 1)


def test_chirality() -> None:
    print("\nchirality — the recorded rotation-for-mirror bug")

    hull = {"id": "hull", "kind": "box", "size": [0.4, 1.0, 0.4], "at": [0, 0.5, 0]}

    # THE RECORDED DEFECT. img2threejs negated x AND z, which is a 180-degree
    # rotation about Y. A rotation preserves handedness, so both halves were
    # the same hand. Measured on the thumb tip: z +0.288 against -0.288.
    rotated = failed_gates(spec([
        hull,
        {"id": "lamp-r", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [0.3, 0.8, 0.288]},
        {"id": "lamp-l", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [-0.3, 0.8, -0.288]},
    ]))
    check(
        "a rotated pair is caught",
        any("ROTATED" in message for message in rotated),
        f"got {rotated}",
    )
    check(
        "the message names the fix",
        any("Negate the lateral axis only" in message for message in rotated),
    )

    translated = failed_gates(spec([
        hull,
        {"id": "lamp-r", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [0.3, 0.8, 0.2]},
        {"id": "lamp-l", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [0.3, 0.8, 0.2]},
    ]))
    check(
        "a pair on the same side is caught",
        any("translated" in message for message in translated),
        f"got {translated}",
    )

    lopsided = failed_gates(spec([
        hull,
        {"id": "lamp-r", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [0.3, 0.8, 0.2]},
        {"id": "lamp-l", "kind": "box", "size": [0.2, 0.1, 0.1], "at": [-0.3, 0.8, 0.2]},
    ]))
    check(
        "a mirrored pair of different sizes is caught",
        any("differ" in message for message in lopsided),
        f"got {lopsided}",
    )

    half = failed_gates(spec([
        hull,
        {"id": "lamp-r", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [0.3, 0.8, 0.2]},
    ]))
    check(
        "a pair with one half missing is caught",
        any("only the right half" in message for message in half),
        f"got {half}",
    )

    # The false positive that would matter most: a correct mirror.
    mirrored = failed_gates(spec([
        hull,
        {"id": "lamp-r", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [0.3, 0.8, 0.2]},
        {"id": "lamp-l", "kind": "box", "size": [0.1, 0.1, 0.1], "at": [-0.3, 0.8, 0.2]},
    ]))
    check("a true reflection passes", not mirrored, f"got {mirrored}")

    # An unpaired part must not be dragged into the pair logic by its name.
    unsuffixed = failed_gates(spec([hull, {
        "id": "barrel", "kind": "cylinder", "size": [0.1, 0.5, 0.1], "at": [0, 0.9, 0],
    }]))
    check("an unpaired part is not treated as half a pair", not unsuffixed, f"got {unsuffixed}")


def test_solidity_and_scale() -> None:
    print("\nsolidity and scale")

    thin = failed_gates(spec([
        {"id": "sheet", "kind": "box", "size": [1.0, 1.0, 1e-7], "at": [0, 0.5, 0]},
    ]))
    check(
        "a zero-thickness part is caught",
        any("edge-on" in message for message in thin),
        f"got {thin}",
    )

    # Real sheet metal must still be allowed, or the gate blocks a door panel.
    plate = failed_gates(spec(
        [{"id": "panel", "kind": "box", "size": [0.8, 2.0, 0.004], "at": [0, 1.0, 0]}],
        height_metres=2.0,
    ))
    check("4 mm sheet metal passes", not plate, f"got {plate}")

    mismatch = failed_gates(spec(
        [{"id": "b", "kind": "box", "size": [0.5, 3.0, 0.5], "at": [0, 1.5, 0]}],
        height_metres=1.0,
    ))
    check(
        "parts disagreeing with the declared height is caught",
        any("declares" in message for message in mismatch),
        f"got {mismatch}",
    )

    decimal = failed_gates(spec(
        [{"id": "door", "kind": "box", "size": [0.01, 0.008, 0.002], "at": [0, 0.004, 0]}],
        height_metres=0.008,
    ))
    check(
        "a misplaced decimal point is caught",
        any("plausible range" in message for message in decimal),
        f"got {decimal}",
    )

    agreeing = failed_gates(spec(
        [{"id": "b", "kind": "box", "size": [0.5, 1.8, 0.5], "at": [0, 0.9, 0]}],
        height_metres=1.8, asset_type="avatar",
    ))
    check("a spec whose size matches its declaration passes", not agreeing, f"got {agreeing}")


def test_budget_and_connectivity() -> None:
    print("\nbudget and connectivity")
    from operators.gen_3d_object.funcs.code_asset import (
        check_connectivity,
        estimate_triangles,
        run_gates,
        validate_spec,
    )

    fat = failed_gates(spec([
        {"id": "ball", "kind": "sphere", "size": [1, 1, 1], "at": [0, 0.5, 0], "segments": 256},
    ]))
    check(
        "a budget overrun is caught",
        any("budget" in message for message in fat),
        f"got {fat}",
    )
    check(
        "the message says to lower segments, not to decimate",
        any("segments" in message for message in fat),
    )

    lean = failed_gates(spec([
        {"id": "ball", "kind": "sphere", "size": [1, 1, 1], "at": [0, 0.5, 0], "segments": 24},
    ]))
    check("a spec inside its budget passes", not lean, f"got {lean}")

    # Floating parts are reported and never failed: a hovering crystal is a
    # design, and failing it would make the gate wrong for a whole class of
    # asset while catching a misplaced wheel either way.
    hovering = validate_spec(spec(
        [
            {"id": "base", "kind": "box", "size": [0.5, 0.5, 0.5], "at": [0, 0.25, 0]},
            {"id": "orb", "kind": "sphere", "size": [0.2, 0.2, 0.2], "at": [0, 1.6, 0]},
        ],
        height_metres=1.7,
    ))
    report = run_gates(hovering)
    check("a hovering part does not fail the spec", report["ok"], f"got {report['failures']}")
    check(
        "a hovering part is reported",
        any("touch nothing" in message for message in report["warnings"]),
        f"got {report['warnings']}",
    )

    connected = check_connectivity(validate_spec(spec([
        {"id": "body", "kind": "box", "size": [0.5, 0.5, 0.5], "at": [0, 0.25, 0]},
        {"id": "lid", "kind": "box", "size": [0.5, 0.05, 0.5], "at": [0, 0.52, 0]},
    ])))
    check(
        "touching parts are not reported as isolated",
        not connected["isolated_parts"],
        f"got {connected['isolated_parts']}",
    )


def test_correction_loop() -> None:
    print("\nbounded correction loop")
    from operators.gen_3d_object.funcs.code_asset import correct_spec, validate_spec

    def wrong(height: float = 3.0) -> dict:
        return validate_spec(spec(
            [{"id": "b", "kind": "box", "size": [0.5, height, 0.5], "at": [0, height / 2, 0]}],
            height_metres=1.0,
        ))

    fixed = correct_spec(wrong(), lambda current, _f: {**current, "height_metres": 3.0})
    check("a reviser that fixes the defect passes", fixed["ok"] and fixed["stop_reason"] == "passed")

    # THE RECORDED FAILURE. An unbounded loop spent 45 minutes recording a car
    # that never moved, because a lookup returned None and nothing raised.
    # Each of these is a way that loop fails to converge, and each must stop.
    stuck = correct_spec(wrong(), lambda current, _f: current)
    check(
        "a reviser that changes nothing stops as `repeating`",
        stuck["stop_reason"] == "repeating",
        f"got {stuck['stop_reason']}",
    )

    def raiser(_current: dict, _failures: list[str]) -> dict:
        raise KeyError("vehicle")

    broke = correct_spec(wrong(), raiser)
    check(
        "a reviser that raises is reported, not swallowed",
        broke["stop_reason"] == "revise_failed" and "KeyError" in broke["detail"],
        f"got {broke}",
    )

    state = {"n": 0}

    def swap(current: dict, _failures: list[str]) -> dict:
        state["n"] += 1
        height = 3.0 if state["n"] % 2 else 4.0
        return {
            **current,
            "parts": [{"id": "b", "kind": "box", "size": [0.5, height, 0.5],
                       "at": [0, height / 2, 0]}],
        }

    stalled = correct_spec(wrong(), swap)
    check(
        "a reviser that makes no progress stops",
        stalled["stop_reason"] in ("repeating", "oscillating", "no_progress"),
        f"got {stalled['stop_reason']}",
    )
    check("the stop reason is explained", bool(stalled.get("detail")))
    check(
        "the least-broken spec is returned, not the last one",
        stalled["spec"]["subject"] == "test rig",
    )


def test_routing() -> None:
    print("\nrouting — declining is a result")
    from operators.gen_3d_object.funcs.code_asset import suits_code_asset

    crate = suits_code_asset("wooden supply crate")
    check("a crate routes to code", crate["suitable"] and crate["route"] == "code")

    face = suits_code_asset("human face", asset_type="avatar")
    check(
        "a face routes to generation",
        not face["suitable"] and face["route"] == "generate",
        f"got {face}",
    )
    check("declining says why", "organic" in face["reason"])

    golem = suits_code_asset("stone golem creature")
    check(
        "a subject reading both ways is ambiguous, not guessed",
        golem["route"] == "ambiguous",
        f"got {golem}",
    )

    unknown = suits_code_asset("zorblatt")
    check("an unknown subject is ambiguous", unknown["route"] == "ambiguous")


def test_glb_output() -> None:
    print("\nGLB output")
    from models.common.glb_utils import glb_json_chunk, glb_summary, is_glb
    from operators.gen_3d_object.funcs.code_asset import build_code_asset

    crate = spec(
        [
            {"id": "body", "kind": "box", "size": [0.6, 0.6, 0.6],
             "at": [0, 0.3, 0], "material": "wood"},
            {"id": "hoop", "kind": "torus", "size": [0.4, 0.4, 0.4],
             "at": [0, 0.5, 0], "material": "iron", "segments": 12},
        ],
        subject="wooden supply crate",
        # 0.7 m, not 0.6: the hoop sits proud of the box, and the composed
        # height is what the scale gate measures. Writing 0.6 here is exactly
        # the declared-versus-actual mismatch the gate is for, and it caught
        # this while the test was being written.
        height_metres=0.7,
        materials={
            "wood": {"baseColor": [0.45, 0.3, 0.18, 1], "roughness": 0.85},
            "iron": {"baseColor": [0.35, 0.35, 0.38, 1], "metallic": 1.0, "roughness": 0.4},
        },
    )

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "crate.glb"
        report = build_code_asset(crate, str(out))
        check("the spec builds", report["ok"], f"got {report['failures']}")
        check("a file was written", out.exists())

        data = out.read_bytes()
        check("the output is a GLB", is_glb(data))

        summary = glb_summary(data)
        check("the GLB parses", "error" not in summary, summary.get("error", ""))
        check(
            "the estimate matches the mesh",
            summary["triangles"] == report["triangles"],
            f"estimated {report['triangles']}, wrote {summary['triangles']}",
        )
        check("both materials survive", summary["materials"] == 2, f"got {summary['materials']}")
        check(
            "the generator is recorded",
            summary["generator"] == "3AGameFactory/glb_writer",
        )

        doc = glb_json_chunk(data)
        # The property a reconstructed mesh cannot offer: parts stay
        # addressable, so gameplay can still move one.
        check(
            "part ids survive as node names",
            [node["name"] for node in doc["nodes"]] == ["body", "hoop"],
            f"got {[node.get('name') for node in doc['nodes']]}",
        )
        check(
            "POSITION carries min/max",
            all(
                "min" in accessor and "max" in accessor
                for accessor in doc["accessors"]
                if accessor["type"] == "VEC3" and "min" in accessor
            ),
        )
        check(
            "the spec is kept inside the file it produced",
            doc["extras"]["gamefactory3a"]["spec"]["subject"] == "wooden supply crate",
        )
        check(
            "facing and size are stated, not inferred",
            report["forward_axis"] == "+z" and report["scale_hint_metres"] == 0.7,
        )

        # `strict` must not write. An asset that exists gets used.
        broken = spec([{"id": "sheet", "kind": "box", "size": [1, 1, 1e-7], "at": [0, 0.5, 0]}])
        blocked = Path(tmp) / "blocked.glb"
        refused = build_code_asset(broken, str(blocked))
        check(
            "a failed gate writes nothing",
            not refused["ok"] and refused["glb_path"] is None and not blocked.exists(),
        )
        check(
            "and says nothing was written",
            any("nothing was written" in message for message in refused["warnings"]),
        )


def test_geometry_is_watertight_enough() -> None:
    print("\ngeometry sanity")
    from models.common.glb_writer import build_part, rotated_bounds

    for kind in ("box", "cylinder", "cone", "sphere", "torus", "lathe", "extrude"):
        part = {
            "id": kind, "kind": kind, "size": (1.0, 1.0, 1.0), "at": (0.0, 0.0, 0.0),
            "rotation": (0.0, 0.0, 0.0), "segments": 12, "profile": None,
            "material": "default",
        }
        positions, normals, indices = build_part(part)
        check(f"{kind}: produces triangles", len(indices) >= 3 and len(indices) % 3 == 0)
        check(f"{kind}: one normal per vertex", len(normals) == len(positions))
        check(
            f"{kind}: every index is in range",
            all(0 <= index < len(positions) for index in indices),
        )
        check(
            f"{kind}: normals are unit length",
            all(
                abs(math.sqrt(x * x + y * y + z * z) - 1.0) < 1e-6
                for x, y, z in normals
            ),
        )
        check(
            f"{kind}: fits its declared extent",
            all(abs(value) <= 0.5 + 1e-6 for point in positions for value in point),
        )

    # The gates and the writer must measure the same object. A draft of
    # `part_bounds` swapped extents for right angles, which is exact at 90
    # degrees and silently wrong at 30 — so a rotation the spec is allowed to
    # use is what this pins down.
    from operators.gen_3d_object.funcs.code_asset import part_bounds

    tilted = {
        "id": "t", "kind": "box", "size": (1.0, 0.2, 0.2), "at": (0.0, 0.0, 0.0),
        "rotation": (0.0, 0.0, 30.0), "segments": 16, "profile": None,
        "material": "default",
    }
    gate_low, gate_high = part_bounds(tilted)
    writer_low, writer_high = rotated_bounds(
        tilted["size"], tilted["at"], tilted["rotation"]
    )
    check(
        "the gates and the writer agree at 30 degrees",
        gate_low == writer_low and gate_high == writer_high,
    )
    positions, _n, _i = build_part(tilted)
    actual_high = max(point[1] for point in positions)
    check(
        "and the bound is the real mesh bound",
        abs(actual_high - gate_high[1]) < 1e-6,
        f"bound {gate_high[1]:.6f}, mesh {actual_high:.6f}",
    )

    # A lathe profile is not confined to the ±size/2 box the other kinds are:
    # it lives in its own coordinates, and measuring it as a unit box made
    # the scale gate disagree with the written mesh by the profile's own
    # extent. Found building a rifle whose barrel measured 1.018 m as a box
    # and 0.41 m as a mesh. Extrude likewise, and under rotation.
    lathe = {
        "id": "l", "kind": "lathe", "size": (1.0, 1.0, 1.0),
        "at": (0.0, 0.118, 0.125), "rotation": (0.0, 0.0, 0.0), "segments": 12,
        "profile": ((0.011, -0.185), (0.011, 0.100), (0.016, 0.225)),
        "material": "default",
    }
    l_low, l_high = part_bounds(lathe)
    l_pos, _n, _i = build_part(lathe)
    l_actual_low = [min(p[axis] for p in l_pos) for axis in range(3)]
    l_actual_high = [max(p[axis] for p in l_pos) for axis in range(3)]
    check(
        "a lathe is measured by its profile, not by its size",
        all(abs(l_low[a] - l_actual_low[a]) < 1e-9
            and abs(l_high[a] - l_actual_high[a]) < 1e-9 for a in range(3)),
        f"bound {l_low}/{l_high} vs mesh {l_actual_low}/{l_actual_high}",
    )

    extruded = {
        "id": "e", "kind": "extrude", "size": (1.0, 1.0, 0.048),
        "at": (0.0, 0.1, 0.0), "rotation": (10.0, 0.0, 0.0), "segments": 12,
        "profile": ((-0.02, -0.25), (0.012, -0.25), (0.012, -0.13), (-0.02, -0.13)),
        "material": "default",
    }
    e_low, e_high = part_bounds(extruded)
    e_pos, _n, _i = build_part(extruded)
    e_actual_low = [min(p[axis] for p in e_pos) for axis in range(3)]
    e_actual_high = [max(p[axis] for p in e_pos) for axis in range(3)]
    check(
        "an extrude under rotation is measured by its profile",
        all(abs(e_low[a] - e_actual_low[a]) < 1e-9
            and abs(e_high[a] - e_actual_high[a]) < 1e-9 for a in range(3)),
        f"bound {e_low}/{e_high} vs mesh {e_actual_low}/{e_actual_high}",
    )


def test_chamfered_box_is_still_a_solid() -> None:
    """A chamfer must change the silhouette without breaking the solid.

    Three properties, each of which a hand-wound bevel gets wrong in a way
    that a screenshot hides. Every undirected edge used exactly twice, or
    the mesh has a hole that only shows once something is behind it. Positive
    signed volume, or some faces wind inward and vanish under backface
    culling in an engine while looking fine in a viewer that does not cull.
    And still inside the unrotated extent box, which is what lets the scale
    and connectivity gates stay ignorant of this field entirely.
    """

    print("\na chamfered box is still a solid")
    from models.common.glb_writer import build_part, rotated_bounds
    from operators.gen_3d_object.funcs.code_asset import (
        MAX_CHAMFER, SpecError, estimate_triangles, validate_spec,
    )

    previous_volume = None
    for chamfer in (0.0, 0.02, 0.12, 0.3, 0.49):
        part = {
            "id": "b", "kind": "box", "size": (0.3, 0.1, 0.7),
            "at": (0.1, 0.2, 0.3), "rotation": (20.0, 35.0, 10.0),
            "segments": 16, "chamfer": chamfer, "material": "default",
        }
        positions, _normals, indices = build_part(part)
        triangles = len(indices) // 3

        edges: dict[frozenset, int] = {}
        for triangle in range(triangles):
            corners = [positions[indices[triangle * 3 + k]] for k in range(3)]
            keys = [tuple(round(v, 9) for v in c) for c in corners]
            for a, b in ((0, 1), (1, 2), (2, 0)):
                edge = frozenset((keys[a], keys[b]))
                edges[edge] = edges.get(edge, 0) + 1
        check(
            f"chamfer {chamfer}: every edge is shared by exactly two triangles",
            all(count == 2 for count in edges.values()),
            f"{sum(1 for c in edges.values() if c != 2)} edges are not shared twice",
        )

        volume = 0.0
        for triangle in range(triangles):
            a, b, c = [positions[indices[triangle * 3 + k]] for k in range(3)]
            volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
        check(
            f"chamfer {chamfer}: every face winds outward",
            volume > 0.0,
            f"signed volume {volume:+.6f}, so some faces face inward",
        )
        if previous_volume is not None:
            check(
                f"chamfer {chamfer}: cutting edges back removes material",
                volume < previous_volume,
                f"volume {volume:.6f} did not fall below {previous_volume:.6f}",
            )
        previous_volume = volume

        low, high = rotated_bounds(part["size"], part["at"], part["rotation"])
        check(
            f"chamfer {chamfer}: the solid stays inside the unchamfered bound",
            all(
                low[axis] - 1e-9 <= min(p[axis] for p in positions)
                and max(p[axis] for p in positions) <= high[axis] + 1e-9
                for axis in range(3)
            ),
            "a chamfered box escaped the box it was cut from",
        )
        check(
            f"chamfer {chamfer}: estimate == mesh",
            estimate_triangles({"parts": [part]}) == triangles,
            f"estimated {estimate_triangles({'parts': [part]})}, wrote {triangles}",
        )

    # Out of range is refused, not clamped: at 0.5 the bevels have eaten the
    # faces they were cutting back and the part is no longer a box, so a spec
    # that still calls it one would be describing something that is not there.
    for bad in (MAX_CHAMFER, 0.8, -0.1):
        try:
            validate_spec({
                "subject": "x", "units": "metres", "forward": "+z",
                "parts": [{"id": "b", "kind": "box", "size": (1.0, 1.0, 1.0),
                           "chamfer": bad}],
            })
            check(f"chamfer {bad} is refused", False, "it was accepted")
        except SpecError:
            check(f"chamfer {bad} is refused", True, "")


def test_every_primitive_is_a_closed_outward_solid() -> None:
    """No primitive may be inside-out, and the writer's normals must agree.

    Written after the rifle's muzzle kept coming out wrong. The cause was
    not the muzzle: `_lathe`, `_cylinder`, `_sphere` and `_torus` all wound
    their quads as (a, b, b+1) where outward is (a, b+1, b), so every lathed,
    cylindrical, spherical and toroidal part in the library was inverted. A
    unit cylinder had a signed volume of -0.26 where the true answer is
    +0.785 — negative because it faced inward, and small because the caps
    were wound correctly and cancelled most of the wall.

    It survived every earlier check because none of them looked. The GLB was
    valid, the triangle counts matched, the bounds were right, and the viewer
    does not cull backfaces, so an inverted solid shades exactly like a
    correct one. It would have appeared first in an engine — the far side of
    the handoff, which is the expensive place to find it.

    Three properties, checked on all seven primitives plus the chamfered box:

    * signed volume positive — every face winds outward
    * no boundary edges — the surface is closed, so "inside" is defined
    * stored normals agree with the triangles' geometric facing, or lighting
      and culling disagree about which side is which
    """

    print("\nevery primitive is a closed, outward-facing solid")
    from models.common.glb_writer import build_part

    quarter_pi = math.pi / 4.0
    cases: tuple[tuple[str, str, dict[str, object], float | None], ...] = (
        ("box", "box", {}, 1.0),
        ("chamfered box", "box", {"chamfer": 0.15}, None),
        ("cylinder", "cylinder", {}, quarter_pi),
        ("cone", "cone", {}, quarter_pi / 3.0),
        ("sphere", "sphere", {}, 4.0 / 3.0 * math.pi * 0.125),
        ("torus", "torus", {}, None),
        ("lathe", "lathe",
         {"profile": ((0.0, -0.5), (0.5, -0.5), (0.5, 0.5), (0.0, 0.5))},
         quarter_pi),
        ("extrude", "extrude",
         {"profile": ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))}, 1.0),
    )

    for label, kind, extra, expected_volume in cases:
        part = {
            "id": kind, "kind": kind, "size": (1.0, 1.0, 1.0),
            "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
            "segments": 96, "profile": None, "material": "default", **extra,
        }
        positions, normals, indices = build_part(part)
        triangles = len(indices) // 3

        volume = 0.0
        opposed = 0
        edges: dict[frozenset, int] = {}
        for triangle in range(triangles):
            a, b, c = [positions[indices[triangle * 3 + k]] for k in range(3)]
            volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0

            edge1 = [b[i] - a[i] for i in range(3)]
            edge2 = [c[i] - b[i] for i in range(3)]
            cross = (
                edge1[1] * edge2[2] - edge1[2] * edge2[1],
                edge1[2] * edge2[0] - edge1[0] * edge2[2],
                edge1[0] * edge2[1] - edge1[1] * edge2[0],
            )
            # Degenerate triangles have no facing to disagree with. They are
            # unavoidable where a lathe profile touches the axis and a whole
            # ring collapses to a point.
            if math.sqrt(sum(v * v for v in cross)) > 1e-12:
                stored = normals[indices[triangle * 3]]
                if sum(cross[i] * stored[i] for i in range(3)) < 0.0:
                    opposed += 1

            keys = [tuple(round(v, 7) for v in point) for point in (a, b, c)]
            for first, second in ((0, 1), (1, 2), (2, 0)):
                edge = frozenset((keys[first], keys[second]))
                edges[edge] = edges.get(edge, 0) + 1

        check(
            f"{label}: signed volume is positive, so it is not inside-out",
            volume > 0.0,
            f"signed volume {volume:+.6f}",
        )
        check(
            f"{label}: the surface is closed",
            not any(count == 1 for count in edges.values()),
            f"{sum(1 for c in edges.values() if c == 1)} boundary edge(s)",
        )
        check(
            f"{label}: stored normals agree with the triangles' facing",
            opposed == 0,
            f"{opposed} of {triangles} triangles face against their normal",
        )
        if expected_volume is not None:
            # At 96 segments the inscribed tessellation is under the true
            # volume by well under a percent. Checking the value and not just
            # its sign is what catches a winding that is reversed on only
            # part of the surface, where the error partly cancels.
            check(
                f"{label}: volume converges on the analytic {expected_volume:.5f}",
                abs(volume - expected_volume) / expected_volume < 0.01,
                f"got {volume:.6f}, expected {expected_volume:.6f}",
            )


def test_a_lathe_profile_that_does_not_close_is_refused() -> None:
    """A lathe profile whose ends leave the axis makes an open tube.

    This is the mistake the rifle's muzzle kept hitting, and it is easy to
    make because the profile reads perfectly sensibly: a list of radii down
    the length of a barrel. But a revolved profile only encloses a volume if
    it starts and ends on the axis of revolution, or the result is a pipe
    with two open ends — no inside, no watertight surface, and a hole through
    which the interior is visible.

    Refused at validation rather than reported by a gate, because unlike a
    proportion or a placement there is no version of this that was intended.
    """

    print("\na lathe profile must close on its axis")
    from operators.gen_3d_object.funcs.code_asset import SpecError, validate_spec

    def spec(profile: object) -> dict:
        return {
            "subject": "turned part", "units": "metres", "forward": "+z",
            "parts": [{
                "id": "p", "kind": "lathe", "size": (1.0, 1.0, 1.0),
                "profile": profile,
            }],
        }

    closed = ((0.0, -0.5), (0.5, -0.5), (0.5, 0.5), (0.0, 0.5))
    validate_spec(spec(closed))
    check("a profile that starts and ends on the axis is accepted", True, "")

    for label, profile in (
        ("both ends off the axis", ((0.5, -0.5), (0.5, 0.5))),
        ("the far end off the axis", ((0.0, -0.5), (0.5, -0.5), (0.5, 0.5))),
        ("the near end off the axis", ((0.5, -0.5), (0.5, 0.5), (0.0, 0.5))),
    ):
        try:
            validate_spec(spec(profile))
            check(f"{label} is refused", False, "it was accepted")
        except SpecError:
            check(f"{label} is refused", True, "")

    for label, profile in (
        ("a negative radius", ((0.0, -0.5), (-0.5, -0.5), (-0.5, 0.5), (0.0, 0.5))),
        ("a single point", ((0.0, 0.0),)),
        ("a non-pair entry", ((0.0, -0.5), (0.5,), (0.0, 0.5))),
    ):
        try:
            validate_spec(spec(profile))
            check(f"{label} is refused", False, "it was accepted")
        except SpecError:
            check(f"{label} is refused", True, "")

    # An extrude outline is a different shape of requirement: it is pushed
    # along z and capped, so it must be a closed loop of at least three
    # points, but it has no axis to touch.
    validate_spec({
        "subject": "extruded part", "units": "metres", "forward": "+z",
        "parts": [{
            "id": "p", "kind": "extrude", "size": (1.0, 1.0, 1.0),
            "profile": ((-0.5, -0.5), (0.5, -0.5), (0.0, 0.5)),
        }],
    })
    check("a three-point extrude outline is accepted", True, "")

    try:
        validate_spec({
            "subject": "extruded part", "units": "metres", "forward": "+z",
            "parts": [{
                "id": "p", "kind": "extrude", "size": (1.0, 1.0, 1.0),
                "profile": ((-0.5, -0.5), (0.5, -0.5)),
            }],
        })
        check("a two-point extrude outline is refused", False, "it was accepted")
    except SpecError:
        check("a two-point extrude outline is refused", True, "")


def test_a_profile_may_be_written_either_way_round() -> None:
    """The direction a profile is traced must not change the solid.

    A stock outline traced clockwise and the same outline traced
    anticlockwise describe the same shape, and both are natural to write. So
    did the rifle's stock, which was traced clockwise and came out
    inside-out while every gate passed — the winding of the walls and caps
    depends on the direction of travel, and the writer had assumed one.

    The alternative to normalising was to document a required direction. That
    puts the burden on whoever writes the spec, for a property they cannot
    check by looking at the render, to prevent a defect that only appears
    after the handoff. Deriving it from the signed area instead means there
    is no wrong way to enter an outline.
    """

    print("\na profile may be traced either way round")
    from models.common.glb_writer import build_part

    def solid(kind: str, profile: tuple) -> tuple[int, float]:
        part = {
            "id": kind, "kind": kind, "size": (1.0, 1.0, 1.0),
            "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
            "segments": 24, "profile": profile, "material": "default",
        }
        positions, _normals, indices = build_part(part)
        volume = 0.0
        for triangle in range(len(indices) // 3):
            a, b, c = [positions[indices[triangle * 3 + k]] for k in range(3)]
            volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
        return len(indices), volume

    # An L-shaped outline, so the test would not pass by symmetry.
    outline = ((-0.4, -0.3), (0.5, -0.3), (0.5, 0.0), (0.1, 0.0),
               (0.1, 0.45), (-0.4, 0.45))
    forward_count, forward_volume = solid("extrude", outline)
    reversed_count, reversed_volume = solid("extrude", tuple(reversed(outline)))
    check(
        "an extrude outline traced clockwise gives the same solid",
        forward_count == reversed_count
        and abs(forward_volume - reversed_volume) < 1e-12,
        f"{forward_volume:+.9f} vs {reversed_volume:+.9f}",
    )
    check(
        "and that solid faces outward whichever way it was traced",
        forward_volume > 0.0 and reversed_volume > 0.0,
        f"{forward_volume:+.9f} / {reversed_volume:+.9f}",
    )

    # A stepped profile, written breech-to-muzzle and then muzzle-to-breech.
    stepped = ((0.0, -0.5), (0.30, -0.5), (0.30, -0.1),
               (0.18, 0.0), (0.18, 0.42), (0.0, 0.5))
    forward_count, forward_volume = solid("lathe", stepped)
    reversed_count, reversed_volume = solid("lathe", tuple(reversed(stepped)))
    check(
        "a lathe profile written from the far end gives the same solid",
        forward_count == reversed_count
        and abs(forward_volume - reversed_volume) < 1e-12,
        f"{forward_volume:+.9f} vs {reversed_volume:+.9f}",
    )
    check(
        "and that solid faces outward whichever end it started from",
        forward_volume > 0.0 and reversed_volume > 0.0,
        f"{forward_volume:+.9f} / {reversed_volume:+.9f}",
    )


def test_the_windings_gate_catches_an_inverted_part() -> None:
    """The gate must fail a solid that is inside-out, and pass one that is not.

    The gate exists because four primitives shipped inverted and every
    other gate passed them. So it is not enough to assert it passes correct
    geometry — that it did before the bug was fixed. It has to be shown
    failing on geometry that is actually inverted, which means reversing a
    real part's triangles and putting that through the gate.
    """

    print("\nthe windings gate catches an inverted part")
    from models.common import glb_writer
    from operators.gen_3d_object.funcs.code_asset import check_windings

    spec = {
        "subject": "turned and boxed part", "units": "metres", "forward": "+z",
        "parts": [
            {"id": "body", "kind": "box", "size": (0.4, 0.4, 0.4),
             "at": (0.0, 0.2, 0.0), "rotation": (0.0, 0.0, 0.0),
             "segments": 16, "profile": None, "material": "default",
             "chamfer": 0.1},
            {"id": "spindle", "kind": "lathe", "size": (1.0, 1.0, 1.0),
             "at": (0.0, 0.2, 0.0), "rotation": (0.0, 0.0, 0.0),
             "segments": 20, "material": "default",
             "profile": ((0.0, -0.2), (0.1, -0.2), (0.08, 0.15), (0.0, 0.2))},
        ],
    }

    report = check_windings(spec)
    check(
        "correct geometry passes the windings gate",
        report["ok"] and not report["inverted"] and not report["unclosed"],
        f"failures: {report['failures']}",
    )

    # Reverse every triangle, which is exactly the defect: same vertices,
    # same bounds, same triangle count, valid GLB, faces pointing inward.
    original = glb_writer.build_part

    def inverted(part: dict) -> tuple:
        positions, normals, indices = original(part)
        flipped = []
        for triangle in range(len(indices) // 3):
            a, b, c = indices[triangle * 3:triangle * 3 + 3]
            flipped.extend([a, c, b])
        return positions, normals, flipped

    glb_writer.build_part = inverted
    try:
        report = check_windings(spec)
    finally:
        glb_writer.build_part = original

    check(
        "an inside-out part fails the windings gate",
        not report["ok"] and len(report["inverted"]) == 2,
        f"ok={report['ok']}, inverted={report['inverted']}",
    )
    check(
        "and the failure says which parts and that they are inside-out",
        any("inside-out" in message for message in report["failures"])
        and any("body" in message and "spindle" in message
                for message in report["failures"]),
        f"failures: {report['failures']}",
    )

    # An unclosed part: a lathe profile whose ends leave the axis. Built
    # directly, bypassing validate_spec, which now refuses this at authoring
    # time — the gate is the second line of defence for a spec that reached
    # the writer another way.
    open_ended = {
        "subject": "open tube", "units": "metres", "forward": "+z",
        "parts": [{
            "id": "tube", "kind": "lathe", "size": (1.0, 1.0, 1.0),
            "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
            "segments": 16, "material": "default",
            "profile": ((0.2, -0.3), (0.2, 0.3)),
        }],
    }
    report = check_windings(open_ended)
    check(
        "a tube with open ends fails the windings gate",
        not report["ok"] and report["unclosed"],
        f"ok={report['ok']}, unclosed={report['unclosed']}",
    )


def test_a_generated_mesh_composes_like_a_primitive() -> None:
    """A `mesh` part must behave as the gates already expect a part to.

    The whole value of composing rather than generating whole is that
    downstream code does not branch on provenance: a generated grip is
    placed by `at`, measured by `part_bounds`, budgeted by
    `estimate_triangles` and checked by `windings` exactly like a box. So
    what is asserted here is *sameness* — every invariant the primitives
    already satisfy, satisfied by a mesh read off disk.

    The fixture is written by this repository's own writer rather than
    checked in as a binary, which also makes the round trip a real test: a
    known mesh out through `write_spec_glb`, back in through
    `read_glb_mesh`, and the triangle count and winding have to survive.

    The one thing that is deliberately *not* the same is the scaling rule.
    A mesh is fitted by a single factor so it keeps the proportions it was
    generated with, because stretching a moulded shape to fill a box is a
    worse defect than a shape that is not exactly the requested thickness.
    That makes `size` a request rather than an extent, which is why the
    bound has to come from the vertices.
    """

    print("\na generated mesh composes like a primitive")
    from models.common.glb_writer import (
        build_part, effective_size, rotated_bounds, write_spec_glb,
    )
    from operators.gen_3d_object.funcs.code_asset import (
        MESH_KIND, SpecError, check_windings, estimate_triangles, run_gates,
        validate_spec,
    )

    with tempfile.TemporaryDirectory() as directory:
        # An L-shaped fixture: not symmetric on any axis, so a bound computed
        # by the wrong rule cannot match by luck.
        fixture = write_spec_glb(
            {
                "subject": "fixture", "units": "metres", "forward": "+z",
                "height_metres": 1.0, "materials": {},
                "parts": [
                    {"id": "tall", "kind": "box", "size": (0.4, 1.0, 0.3),
                     "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
                     "segments": 16, "profile": None, "material": "d"},
                    {"id": "foot", "kind": "box", "size": (0.9, 0.2, 0.3),
                     "at": (0.25, -0.4, 0.0), "rotation": (0.0, 0.0, 0.0),
                     "segments": 16, "profile": None, "material": "d"},
                ],
            },
            str(Path(directory) / "fixture.glb"),
        )
        fixture_triangles = 24        # two sharp boxes

        def part(size, rotation=(0.0, 0.0, 0.0), at=(0.0, 0.2, 0.0)):
            return {
                "id": "generated", "kind": MESH_KIND, "source": fixture,
                "size": size, "at": at, "rotation": rotation,
                "segments": 16, "profile": None, "material": "default",
            }

        positions, normals, indices = build_part(part((0.5, 0.5, 0.5)))
        check(
            "the fixture survives the round trip with its triangles intact",
            len(indices) // 3 == fixture_triangles,
            f"wrote {fixture_triangles}, read back {len(indices) // 3}",
        )
        check(
            "and with a normal per vertex",
            len(normals) == len(positions),
            f"{len(positions)} positions, {len(normals)} normals",
        )

        check(
            "the triangle estimate reads the file rather than guessing",
            estimate_triangles({"parts": [part((0.5, 0.5, 0.5))]})
            == fixture_triangles,
            f"estimated "
            f"{estimate_triangles({'parts': [part((0.5, 0.5, 0.5))]})}",
        )

        # The bound must equal the mesh at any angle. A box's bound can be had
        # from its eight transformed corners; a mesh that does not reach its
        # corners cannot, and the discrepancy only appears once rotated.
        for rotation in ((0.0, 0.0, 0.0), (0.0, 90.0, 0.0), (-8.0, 0.0, 0.0),
                         (23.0, 41.0, 17.0)):
            candidate = part((0.5, 0.5, 0.5), rotation=rotation)
            placed, _normals, _indices = build_part(candidate)
            actual_low = [min(p[axis] for p in placed) for axis in range(3)]
            actual_high = [max(p[axis] for p in placed) for axis in range(3)]
            low, high = rotated_bounds(
                candidate["size"], candidate["at"], rotation,
                kind=MESH_KIND, source=fixture,
            )
            check(
                f"the bound equals the mesh at rotation {rotation}",
                all(
                    abs(low[axis] - actual_low[axis]) < 1e-9
                    and abs(high[axis] - actual_high[axis]) < 1e-9
                    for axis in range(3)
                ),
                f"bound {[round(v, 6) for v in low]}..."
                f"{[round(v, 6) for v in high]} against mesh "
                f"{[round(v, 6) for v in actual_low]}..."
                f"{[round(v, 6) for v in actual_high]}",
            )

        # A non-uniform size is reduced to its largest component, and both the
        # writer and the bound have to agree about that. Disagreeing is the
        # defect the lathe bounds already produced once.
        check(
            "a non-uniform size on a mesh part collapses to one factor",
            effective_size((0.5, 0.1, 0.2), MESH_KIND) == (0.5, 0.5, 0.5),
            f"got {effective_size((0.5, 0.1, 0.2), MESH_KIND)}",
        )
        stretched, _n, _i = build_part(part((0.5, 0.1, 0.2)))
        uniform, _n, _i = build_part(part((0.5, 0.5, 0.5)))
        check(
            "so it writes the same mesh as the uniform request",
            all(
                abs(stretched[index][axis] - uniform[index][axis]) < 1e-12
                for index in range(len(uniform)) for axis in range(3)
            ),
            "a non-uniform size changed the geometry",
        )

        # `windings` treats the mesh like everything else, because it is
        # measuring the evaluated triangles and does not know the provenance.
        report = check_windings({"parts": [part((0.5, 0.5, 0.5))]})
        check(
            "the windings gate passes a well-formed generated part",
            report["ok"] and not report["inverted"],
            f"failures: {report['failures']}",
        )

        # And the composition as a whole passes, which is the claim: a spec
        # mixing the two kinds is not a special case anywhere.
        mixed = validate_spec({
            "subject": "bracket with a moulded pad", "units": "metres",
            "forward": "+z", "asset_type": "prop", "height_metres": 0.5,
            "materials": {},
            "parts": [
                {"id": "plate", "kind": "box", "size": (0.3, 0.02, 0.3),
                 "at": (0.0, 0.01, 0.0), "material": "default",
                 "chamfer": 0.1},
                {"id": "pad", "kind": MESH_KIND, "source": fixture,
                 "size": (0.5, 0.5, 0.5), "at": (0.0, 0.27, 0.0),
                 "material": "default"},
            ],
        })
        gates = run_gates(mixed)
        check(
            "a spec mixing primitives and generated parts passes every gate",
            gates["ok"],
            f"failures: {gates['failures']}",
        )
        check(
            "and the provenance gate reports which parts were generated",
            [
                entry["id"]
                for report in gates["reports"] if report["gate"] == "provenance"
                for entry in report["generated_parts"]
            ] == ["pad"],
            f"reports: {[r['gate'] for r in gates['reports']]}",
        )

        # Refusals. A missing source and a source on a primitive are both
        # authoring mistakes with no version that was intended: the first has
        # no geometry at all, and the second is a generated part that was
        # meant to be one and silently is not.
        for label, faulty in (
            ("a mesh part with no source", {"id": "p", "kind": MESH_KIND,
                                            "size": (0.5, 0.5, 0.5)}),
            ("a mesh part whose source is missing", {
                "id": "p", "kind": MESH_KIND, "size": (0.5, 0.5, 0.5),
                "source": str(Path(directory) / "absent.glb")}),
            ("a source on a box", {"id": "p", "kind": "box",
                                   "size": (0.5, 0.5, 0.5),
                                   "source": fixture}),
        ):
            try:
                validate_spec({
                    "subject": "x", "units": "metres", "forward": "+z",
                    "parts": [faulty],
                })
                check(f"{label} is refused", False, "it was accepted")
            except SpecError:
                check(f"{label} is refused", True, "")


def test_the_provenance_gate_reports_the_trade() -> None:
    """The gate must say what generation bought and what it cost.

    Its job is not to prevent generated parts — it is to keep the trade
    visible, because after export the two kinds are indistinguishable and
    only one of them can still be adjusted by editing a number. Two
    thresholds, and the reason they differ is the point:

    A composition that is mostly generated triangles is warned, since a
    grip and a stock legitimately outweigh forty small primitives.

    A composition that is mostly generated *parts as well as* triangles is
    failed, because at that point it is a generated asset with primitives
    attached, and it would be reported as `verified_by="spec"` while
    nothing had verified the facing of the mesh carrying it.
    """

    print("\nthe provenance gate reports the trade")
    from models.common.glb_writer import write_spec_glb
    from operators.gen_3d_object.funcs.code_asset import (
        MESH_KIND, check_provenance, validate_spec,
    )

    with tempfile.TemporaryDirectory() as directory:
        # A dense fixture, so a single mesh part can dominate a budget the way
        # a real generated part does.
        fixture = write_spec_glb(
            {
                "subject": "dense", "units": "metres", "forward": "+z",
                "height_metres": 1.0, "materials": {},
                "parts": [{
                    "id": "ball", "kind": "sphere", "size": (1.0, 1.0, 1.0),
                    "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
                    "segments": 48, "profile": None, "material": "d",
                }],
            },
            str(Path(directory) / "dense.glb"),
        )

        def spec(parts: list[dict]) -> dict:
            return validate_spec({
                "subject": "assembly", "units": "metres", "forward": "+z",
                "asset_type": "prop", "materials": {}, "parts": parts,
            })

        primitives = [
            {"id": f"box-{index}", "kind": "box", "size": (0.05, 0.05, 0.05),
             "at": (index * 0.06, 0.03, 0.0), "material": "default"}
            for index in range(6)
        ]
        mesh_part = {
            "id": "moulded", "kind": MESH_KIND, "source": fixture,
            "size": (0.2, 0.2, 0.2), "at": (0.0, 0.2, 0.0),
            "material": "default",
        }

        # No generated parts: the gate is silent rather than absent, so a
        # pure-primitive spec does not pay for a check it does not need.
        report = check_provenance(spec(primitives))
        check(
            "a spec with no generated parts passes silently",
            report["ok"] and not report["warnings"]
            and report["generated_triangles"] == 0,
            f"{report}",
        )

        # Mostly generated triangles: warned, not failed.
        report = check_provenance(spec(primitives + [mesh_part]))
        check(
            "a composition dominated by generated triangles is warned",
            report["ok"] and any(
                "generated" in message for message in report["warnings"]
            ),
            f"ok={report['ok']}, warnings={report['warnings']}",
        )
        check(
            "and the per-part cost is reported, not just the total",
            report["generated_parts"][0]["triangles"] > 0
            and 0.0 < report["generated_parts"][0]["share"] <= 1.0,
            f"{report['generated_parts']}",
        )

        # Mostly generated parts *and* triangles: failed.
        report = check_provenance(spec([
            dict(mesh_part, id="moulded-a"),
            dict(mesh_part, id="moulded-b", at=(0.3, 0.2, 0.0)),
            {"id": "pin", "kind": "box", "size": (0.01, 0.01, 0.01),
             "at": (0.0, 0.005, 0.0), "material": "default"},
        ]))
        check(
            "a composition that is really a generated asset is failed",
            not report["ok"]
            and any("composition" in message for message in report["failures"]),
            f"ok={report['ok']}, failures={report['failures']}",
        )

        # The boundary, pinned. Both conditions are required, and each on its
        # own would fail work that is correct: a real weapon is 77% generated
        # triangles because a grip outweighs forty small primitives, and a
        # bracket is legitimately one plate plus one moulded pad. Asserting
        # only the failing case would leave the threshold as a claim.
        report = check_provenance(spec([
            {"id": "plate", "kind": "box", "size": (0.3, 0.02, 0.3),
             "at": (0.0, 0.01, 0.0), "material": "default"},
            {"id": "post", "kind": "cylinder", "size": (0.02, 0.1, 0.02),
             "at": (0.0, 0.07, 0.0), "material": "default"},
            dict(mesh_part, id="pad"),
        ]))
        check(
            "two stated parts beside a generated one is a composition, not a "
            "disguise",
            report["ok"] and report["generated_share"] > 0.9,
            f"ok={report['ok']}, share={report['generated_share']}, "
            f"failures={report['failures']}",
        )
        report = check_provenance(spec([
            {"id": "plate", "kind": "box", "size": (0.3, 0.02, 0.3),
             "at": (0.0, 0.01, 0.0), "material": "default"},
            dict(mesh_part, id="pad"),
        ]))
        check(
            "but one stated part beside it is decoration on something fetched",
            not report["ok"],
            f"ok={report['ok']}, share={report['generated_share']}",
        )

        # A non-uniform size is honoured by taking the largest component, and
        # the gate says so — the author wrote three numbers and got one.
        report = check_provenance(spec([
            dict(mesh_part, size=(0.2, 0.05, 0.1)),
        ]))
        check(
            "a non-uniform size on a generated part is called out",
            any("not uniform" in message for message in report["warnings"]),
            f"warnings={report['warnings']}",
        )
        report = check_provenance(spec([mesh_part]))
        check(
            "and a uniform one is not",
            not any("not uniform" in message for message in report["warnings"]),
            f"warnings={report['warnings']}",
        )


def test_an_unclosed_generated_part_warns_but_does_not_block() -> None:
    """An unclosed mesh is warned; an unclosed primitive still fails.

    The same measurement, two different meanings, and collapsing them
    either way is wrong. An unclosed *primitive* has a fix in the spec —
    nearly always a lathe profile that does not return to the axis — so
    failing it is actionable. An unclosed *generated* mesh is what the
    generator returned; no spec edit repairs it, and blocking an asset over
    a few boundary edges on a grip means the gate gets bypassed rather than
    the mesh improved, and then it protects nothing.

    Measured on a real fetched part: the scope generated for the rifle came
    back with 103 boundary edges while the grip and stock had none, so this
    is the common case and not a hypothetical.
    """

    print("\nan unclosed generated part warns but does not block")
    from models.common import glb_writer
    from operators.gen_3d_object.funcs.code_asset import MESH_KIND, check_windings

    with tempfile.TemporaryDirectory() as directory:
        fixture = glb_writer.write_spec_glb(
            {
                "subject": "cube", "units": "metres", "forward": "+z",
                "height_metres": 1.0, "materials": {},
                "parts": [{
                    "id": "c", "kind": "box", "size": (1.0, 1.0, 1.0),
                    "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
                    "segments": 16, "profile": None, "material": "d",
                }],
            },
            str(Path(directory) / "cube.glb"),
        )

        mesh_part = {
            "id": "fetched", "kind": MESH_KIND, "source": fixture,
            "size": (0.3, 0.3, 0.3), "at": (0.0, 0.15, 0.0),
            "rotation": (0.0, 0.0, 0.0), "segments": 16, "profile": None,
            "material": "default",
        }
        box_part = {
            "id": "authored", "kind": "box", "size": (0.3, 0.3, 0.3),
            "at": (0.4, 0.15, 0.0), "rotation": (0.0, 0.0, 0.0),
            "segments": 16, "profile": None, "material": "default",
            "chamfer": 0.0,
        }

        # Drop the last triangle of whatever is built, which opens a hole
        # without touching anything else — same vertices, same bounds.
        original = glb_writer.build_part

        def holed(part: dict) -> tuple:
            positions, normals, indices = original(part)
            return positions, normals, indices[:-3]

        glb_writer.build_part = holed
        try:
            report = check_windings({"parts": [mesh_part]})
            check(
                "an unclosed generated part does not block",
                report["ok"] and report["unclosed_generated"]
                and not report["unclosed"],
                f"ok={report['ok']}, generated={report['unclosed_generated']}, "
                f"primitive={report['unclosed']}",
            )
            check(
                "and it is warned about by name",
                any("fetched" in message for message in report["warnings"]),
                f"warnings={report['warnings']}",
            )

            report = check_windings({"parts": [box_part]})
            check(
                "an unclosed primitive still fails",
                not report["ok"] and report["unclosed"]
                and not report["unclosed_generated"],
                f"ok={report['ok']}, primitive={report['unclosed']}",
            )
        finally:
            glb_writer.build_part = original


def test_a_fetched_texture_survives_composition() -> None:
    """A generated part's UVs and base-colour image must reach the output.

    This is most of what a generated part contributes. A grip's stippling
    and a car shell's panel decals live in the atlas, not the mesh, so a
    composition that drops the texture has paid for geometry and thrown
    away the reason it was fetched — while still looking plausible, because
    the part inherits the spec's flat PBR factors and merely appears
    undecorated rather than broken.

    Four properties, each of which fails silently:

    * UVs are written, and only for the parts that have them. A primitive
      given arbitrary UVs samples an arbitrary corner of somebody else's
      atlas, which is worse than no texture at all.
    * the image bytes are carried, so the output is self-contained. A GLB
      referencing an external file is not something an engine import can use.
    * one copy per source, however many times the part is placed. Four
      identical wheels sharing a 3 MB atlas is 3 MB; not sharing it is 12.
    * a metallic-roughness *map* means its factors cannot be inherited.
      Measured on the fetched grip: `metallicFactor 1.0, roughnessFactor
      1.0`, which are glTF defaults meant to multiply a map. Copied across
      without the map they scale, a stippled polymer grip renders as
      sandblasted steel.
    """

    print("\na fetched texture survives composition")
    from models.common.glb_utils import glb_json_chunk, read_glb_mesh
    from models.common.glb_writer import load_mesh_asset, write_spec_glb

    # A fixture with a base-colour texture, built by hand rather than fetched
    # so the test needs no network and no checked-in binary. A 1x1 PNG is
    # enough: what is under test is the plumbing, not the image.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080200000090"
        "7753de0000000c4944415408d763f8cfc0000003010100189dd1a2000000"
        "0049454e44ae426082"
    )

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "textured.glb"
        _write_textured_fixture(source, png)

        asset = load_mesh_asset(str(source))
        check(
            "the fixture's UVs are read back",
            asset["has_uvs"] and len(asset["uvs"]) == len(asset["positions"]),
            f"has_uvs={asset['has_uvs']}, "
            f"{len(asset['uvs'])} uvs for {len(asset['positions'])} vertices",
        )
        check(
            "and its base-colour image bytes",
            asset["materials"] and asset["materials"][0]["image"] == png,
            f"materials={[m['name'] for m in asset['materials']]}",
        )
        check(
            "a metallic-roughness map makes its factors untrustworthy",
            asset["materials"][0]["factors_from"] == "assumed"
            and asset["materials"][0]["metallic"] == 0.0,
            f"factors_from={asset['materials'][0]['factors_from']}, "
            f"metallic={asset['materials'][0]['metallic']}",
        )

        # Compose: one primitive, and the same fetched part placed twice.
        def mesh_part(part_id: str, at: tuple) -> dict:
            return {
                "id": part_id, "kind": "mesh", "source": str(source),
                "size": (0.3, 0.3, 0.3), "at": at, "rotation": (0.0, 0.0, 0.0),
                "segments": 16, "profile": None, "material": "steel",
                "chamfer": 0.0, "long_axis": None,
            }

        out = write_spec_glb(
            {
                "subject": "two pads on a plate", "units": "metres",
                "forward": "+z", "height_metres": 0.5,
                "materials": {"steel": {"baseColor": [0.5, 0.5, 0.55, 1.0],
                                        "metallic": 1.0, "roughness": 0.3}},
                "parts": [
                    {"id": "plate", "kind": "box", "size": (0.6, 0.02, 0.6),
                     "at": (0.0, 0.01, 0.0), "rotation": (0.0, 0.0, 0.0),
                     "segments": 16, "profile": None, "material": "steel",
                     "chamfer": 0.1, "source": None, "long_axis": None},
                    mesh_part("pad-a", (-0.2, 0.16, 0.0)),
                    mesh_part("pad-b", (0.2, 0.16, 0.0)),
                ],
            },
            str(Path(directory) / "composed.glb"),
        )
        document = glb_json_chunk(Path(out).read_bytes())

        textured = [
            "TEXCOORD_0" in primitive["attributes"]
            for mesh in document["meshes"] for primitive in mesh["primitives"]
        ]
        check(
            "UVs are written for the fetched parts and not the primitive",
            textured == [False, True, True],
            f"per-primitive TEXCOORD_0: {textured}",
        )
        check(
            "the image travels inside the GLB, so it is self-contained",
            len(document.get("images", [])) == 1
            and "bufferView" in document["images"][0],
            f"images={document.get('images')}",
        )
        check(
            "one image for two placements of the same source",
            len(document.get("textures", [])) == 1,
            f"{len(document.get('textures', []))} textures for two placements",
        )
        check(
            "and a sampler is stated rather than left to the importer",
            len(document.get("samplers", [])) == 1,
            f"samplers={document.get('samplers')}",
        )
        check(
            "the primitive keeps the spec's own material",
            any(material["name"] == "steel"
                for material in document["materials"]),
            f"materials={[m['name'] for m in document['materials']]}",
        )

        back = read_glb_mesh(Path(out).read_bytes())
        check(
            "the composed file round-trips with its UVs",
            back["has_uvs"] and len(back["uvs"]) == len(back["positions"]),
            f"has_uvs={back['has_uvs']}",
        )


def _write_textured_fixture(path: Path, png: bytes) -> None:
    """A minimal GLB: one textured quad, with UVs and a metallic-roughness map.

    Written by hand because the point is to exercise the *reader* against a
    file this repository's writer did not produce — a fixture round-tripped
    through our own writer would only prove the two agree, which is exactly
    the assumption that lets a decoding bug survive.
    """

    import json as json_module
    import struct as struct_module

    positions = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0),
                 (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)]
    normals = [(0.0, 0.0, 1.0)] * 4
    uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    indices = [0, 1, 2, 0, 2, 3]

    buffer = bytearray()
    views: list[dict] = []

    def add(payload: bytes, target: int | None = None) -> int:
        while len(buffer) % 4:
            buffer.append(0)
        view = {"buffer": 0, "byteOffset": len(buffer), "byteLength": len(payload)}
        if target is not None:
            view["target"] = target
        buffer.extend(payload)
        views.append(view)
        return len(views) - 1

    position_view = add(b"".join(struct_module.pack("<3f", *p) for p in positions), 34962)
    normal_view = add(b"".join(struct_module.pack("<3f", *n) for n in normals), 34962)
    uv_view = add(b"".join(struct_module.pack("<2f", *t) for t in uvs), 34962)
    index_view = add(b"".join(struct_module.pack("<H", i) for i in indices), 34963)
    image_view = add(png)

    document = {
        "asset": {"version": "2.0", "generator": "test fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        # A node transform, so the reader has to apply one.
        "nodes": [{"mesh": 0, "translation": [0.0, 0.25, 0.0],
                   "scale": [2.0, 2.0, 2.0]}],
        "meshes": [{"primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
            "indices": 3, "material": 0, "mode": 4,
        }]}],
        "materials": [{
            "name": "painted",
            "pbrMetallicRoughness": {
                "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                # The defaults an exporter leaves behind when the channels are
                # in a map. Inheriting them is the defect under test.
                "metallicFactor": 1.0,
                "roughnessFactor": 1.0,
                "baseColorTexture": {"index": 0},
                "metallicRoughnessTexture": {"index": 1},
            },
        }],
        "textures": [{"source": 0}, {"source": 0}],
        "images": [{"bufferView": image_view, "mimeType": "image/png"}],
        "accessors": [
            {"bufferView": position_view, "componentType": 5126, "count": 4,
             "type": "VEC3", "min": [-0.5, -0.5, 0.0], "max": [0.5, 0.5, 0.0]},
            {"bufferView": normal_view, "componentType": 5126, "count": 4,
             "type": "VEC3"},
            {"bufferView": uv_view, "componentType": 5126, "count": 4,
             "type": "VEC2"},
            {"bufferView": index_view, "componentType": 5123, "count": 6,
             "type": "SCALAR"},
        ],
        "bufferViews": views,
        "buffers": [{"byteLength": len(buffer)}],
    }

    json_chunk = bytearray(json_module.dumps(document).encode("utf-8"))
    while len(json_chunk) % 4:
        json_chunk.append(ord(" "))
    binary_chunk = bytearray(buffer)
    while len(binary_chunk) % 4:
        binary_chunk.append(0)

    total = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    with open(path, "wb") as handle:
        handle.write(struct_module.pack("<4sII", b"glTF", 2, total))
        handle.write(struct_module.pack("<I4s", len(json_chunk), b"JSON"))
        handle.write(json_chunk)
        handle.write(struct_module.pack("<I4s", len(binary_chunk), b"BIN\x00"))
        handle.write(binary_chunk)


def test_the_orientation_gate_catches_a_sideways_part() -> None:
    """A generated part's declared long axis must match where it lands.

    Written after the rifle's grip came out facing across the weapon. The
    mesh's own longest axis was its x, so `rotation: [-8, 0, 0]` — the
    intuitive reading of "rake it back" — tilted it in the plane it was
    already flat in. Every other gate passed: the bounds were right, the
    winding was right, the scale was right, and the part was sideways.

    The reason no other gate can see this is that nothing in a generated
    file says which of its axes is length. So the spec has to say, and the
    check has to be against the placed vertices.

    It is also why the same rotation cannot be carried from one version of a
    part to the next: regenerating the grip textured produced a file whose
    correct rotation was `+90` where the previous one needed `-90`. A new
    file is a new set of axes.
    """

    print("\nthe orientation gate catches a sideways part")
    from models.common.glb_writer import write_spec_glb
    from operators.gen_3d_object.funcs.code_asset import (
        MESH_KIND, SpecError, check_orientation, validate_spec,
    )

    with tempfile.TemporaryDirectory() as directory:
        # A part that is clearly longest on its own y, so a rotation that
        # moves it is unambiguous.
        source = write_spec_glb(
            {
                "subject": "post", "units": "metres", "forward": "+z",
                "height_metres": 1.0, "materials": {},
                "parts": [{
                    "id": "p", "kind": "box", "size": (0.2, 1.0, 0.3),
                    "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
                    "segments": 16, "profile": None, "material": "d",
                }],
            },
            str(Path(directory) / "post.glb"),
        )

        def spec(rotation: tuple, long_axis: str | None) -> dict:
            part = {
                "id": "post", "kind": MESH_KIND, "source": source,
                "size": (0.5, 0.5, 0.5), "at": (0.0, 0.25, 0.0),
                "rotation": rotation, "material": "default",
            }
            if long_axis:
                part["long_axis"] = long_axis
            return validate_spec({
                "subject": "a post", "units": "metres", "forward": "+z",
                "parts": [part],
            })

        report = check_orientation(spec((0.0, 0.0, 0.0), "y"))
        check(
            "an upright part declared upright passes",
            not report["warnings"],
            f"warnings={report['warnings']}",
        )

        # Laid on its side but still claiming y: the defect.
        report = check_orientation(spec((0.0, 0.0, 90.0), "y"))
        check(
            "a part rotated onto its side is caught",
            any("long_axis" in message for message in report["warnings"]),
            f"warnings={report['warnings']}",
        )
        check(
            "and the measured axis is reported so the fix is obvious",
            report["parts_checked"][0]["measured_long_axis"] == "x",
            f"{report['parts_checked'][0]}",
        )

        # Rotated *and* declared correctly: no warning. Asserting only the
        # failing case would leave a gate that fires on any rotation at all.
        report = check_orientation(spec((0.0, 0.0, 90.0), "x"))
        check(
            "a part rotated onto its side and declared so passes",
            not report["warnings"],
            f"warnings={report['warnings']}",
        )

        # Undeclared: silent. The field is optional because for a near-cubic
        # part the longest axis is noise, and a gate that demanded a
        # declaration nobody could give would be bypassed.
        report = check_orientation(spec((0.0, 0.0, 90.0), None))
        check(
            "an undeclared long axis is not guessed at",
            not report["warnings"] and report["parts_checked"],
            f"warnings={report['warnings']}",
        )

        # A near-cubic part is skipped rather than judged on noise.
        cube = write_spec_glb(
            {
                "subject": "cube", "units": "metres", "forward": "+z",
                "height_metres": 1.0, "materials": {},
                "parts": [{
                    "id": "c", "kind": "box", "size": (1.0, 1.0, 1.0),
                    "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
                    "segments": 16, "profile": None, "material": "d",
                }],
            },
            str(Path(directory) / "cube.glb"),
        )
        report = check_orientation(validate_spec({
            "subject": "a cube", "units": "metres", "forward": "+z",
            "parts": [{
                "id": "cube", "kind": MESH_KIND, "source": cube,
                "size": (0.5, 0.5, 0.5), "at": (0.0, 0.25, 0.0),
                "long_axis": "z",
            }],
        }))
        check(
            "a part with no dominant axis is skipped, not failed on noise",
            not report["warnings"]
            and report["parts_checked"][0].get("skipped"),
            f"{report['parts_checked'][0]}",
        )

        # Refusals: a bad axis name, and the field on a primitive.
        for label, part in (
            ("an unknown axis name", {
                "id": "p", "kind": MESH_KIND, "source": source,
                "size": (0.5, 0.5, 0.5), "long_axis": "up"}),
            ("long_axis on a box", {
                "id": "p", "kind": "box", "size": (0.5, 0.5, 0.5),
                "long_axis": "y"}),
        ):
            try:
                validate_spec({
                    "subject": "x", "units": "metres", "forward": "+z",
                    "parts": [part],
                })
                check(f"{label} is refused", False, "it was accepted")
            except SpecError:
                check(f"{label} is refused", True, "")


def test_estimate_matches_every_primitive() -> None:
    """The budget gate must count what the writer actually emits.

    Pinned per primitive and per segment count because the first draft used
    `segments ** 2` for the round shapes where the writer rings them at
    `segments // 2`. That over-counted by exactly 2x, so the budget gate
    would have rejected meshes that were inside their budget — and a gate
    that rejects good work gets bypassed, after which it protects nothing.
    """

    print("\nthe estimate is the mesh")
    from models.common.glb_writer import build_part
    from operators.gen_3d_object.funcs.code_asset import estimate_triangles

    profiles = {
        "lathe": ((0.5, -0.5), (0.4, 0.0), (0.5, 0.5)),
        "extrude": ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (0.0, 0.6), (-0.5, 0.5)),
    }
    for kind in ("box", "cylinder", "cone", "sphere", "torus", "lathe", "extrude"):
        for segments in (3, 8, 12, 16, 32):
            part = {
                "id": kind, "kind": kind, "size": (1.0, 1.0, 1.0),
                "at": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0),
                "segments": segments, "profile": profiles.get(kind),
                "material": "default",
            }
            _positions, _normals, indices = build_part(part)
            actual = len(indices) // 3
            estimated = estimate_triangles({"parts": [part]})
            check(
                f"{kind} at {segments} segments: estimate == mesh",
                actual == estimated,
                f"estimated {estimated}, wrote {actual}",
            )


def main() -> int:
    print(__doc__.strip().split("\n")[2])
    test_validation()
    test_chirality()
    test_solidity_and_scale()
    test_budget_and_connectivity()
    test_correction_loop()
    test_routing()
    test_glb_output()
    test_geometry_is_watertight_enough()
    test_chamfered_box_is_still_a_solid()
    test_every_primitive_is_a_closed_outward_solid()
    test_a_lathe_profile_that_does_not_close_is_refused()
    test_a_profile_may_be_written_either_way_round()
    test_the_windings_gate_catches_an_inverted_part()
    test_a_generated_mesh_composes_like_a_primitive()
    test_the_provenance_gate_reports_the_trade()
    test_an_unclosed_generated_part_warns_but_does_not_block()
    test_a_fetched_texture_survives_composition()
    test_the_orientation_gate_catches_a_sideways_part()
    test_estimate_matches_every_primitive()

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for failure in FAILED:
        print(f"  - {failure}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
