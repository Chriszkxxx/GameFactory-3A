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
    test_estimate_matches_every_primitive()

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for failure in FAILED:
        print(f"  - {failure}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
