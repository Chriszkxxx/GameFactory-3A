"""
models/common/glb_writer.py

Write a binary glTF (`.glb`) from a declarative part spec, with nothing but
the standard library.

This is the write half of `glb_utils.py`, and it exists for the same reason:
the asset path has to work on a CPU-only box with nothing installed. Reaching
for `trimesh` here would make a spec-built crate depend on a numpy/scipy stack
that the spec route exists partly to avoid.

WHY glTF AND NOT A PER-ENGINE FORMAT. Measured from each adapter's own
importer, the formats accepted are:

    UE5        fbx glb gltf obj usd usda usdz
    Blender    abc fbx glb gltf obj ply usd usda usdc usdz
    Unity      fbx glb gltf obj
    three.js   glb gltf

glTF is the intersection, so one writer serves every engine and the spec
route needs no per-engine emitter to be useful on day one.

THIS MODULE IS THE SINGLE SOURCE OF TRUTH FOR PART GEOMETRY. The gates in
`operators/gen_3d_object/funcs/code_asset.py` import `rotated_bounds` from
here rather than computing extents their own way. That is deliberate: a gate
that measured the spec differently from the writer would pass a mesh that
was not the mesh being written, which is the same class of silent wrong
answer as an inverted bounding-box convention.

Usage:
    from models.common.glb_writer import write_spec_glb
    write_spec_glb(spec, "model.glb")     # spec: see code_asset.validate_spec
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any, Iterable, Sequence

#: glTF component types used here.
_FLOAT = 5126
_UNSIGNED_INT = 5125

#: glTF primitive mode 4 == TRIANGLES.
_MODE_TRIANGLES = 4

#: Written into `asset.generator`, so a spec-built mesh is identifiable
#: after the fact. `glb_summary` reads this back.
GENERATOR = "3AGameFactory/glb_writer"

#: Default PBR factors for a material a spec did not describe. Mid-grey
#: dielectric: visible under any lighting, obviously placeholder, and never
#: mistaken for authored art.
DEFAULT_MATERIAL: dict[str, Any] = {
    "baseColor": [0.72, 0.72, 0.74, 1.0],
    "metallic": 0.0,
    "roughness": 0.6,
}

Vec3 = tuple[float, float, float]


# --------------------------------------------------------------------------
# Transform maths, shared with the gates
# --------------------------------------------------------------------------


def euler_matrix(rotation: Sequence[float]) -> tuple[Vec3, Vec3, Vec3]:
    """Row-major rotation matrix for XYZ Euler angles in **degrees**.

    Applied X, then Y, then Z. Stated because the order is not discoverable
    from a result that looks plausible, and a spec authored against one
    convention and evaluated under another produces a mesh that is subtly,
    consistently wrong.
    """

    x, y, z = (math.radians(float(value)) for value in rotation)
    sx, cx = math.sin(x), math.cos(x)
    sy, cy = math.sin(y), math.cos(y)
    sz, cz = math.sin(z), math.cos(z)
    return (
        (cy * cz, cz * sx * sy - cx * sz, cx * cz * sy + sx * sz),
        (cy * sz, cx * cz + sx * sy * sz, -cz * sx + cx * sy * sz),
        (-sy, cy * sx, cx * cy),
    )


def apply_matrix(matrix: tuple[Vec3, Vec3, Vec3], point: Sequence[float]) -> Vec3:
    """Rotate a point or a direction by `matrix`."""
    x, y, z = (float(value) for value in point)
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z,
    )


def rotated_bounds(
    size: Sequence[float],
    at: Sequence[float],
    rotation: Sequence[float],
) -> tuple[Vec3, Vec3]:
    """Axis-aligned `(low, high)` of a rotated, translated box.

    Every one of the eight corners is transformed and the extremes taken,
    rather than swapping extents for the right-angle cases. Exact for a box
    at any angle, and a true bound for the round primitives, whose surface
    is inside their extent box.
    """

    matrix = euler_matrix(rotation)
    half = [float(value) / 2.0 for value in size]
    low = [float("inf")] * 3
    high = [float("-inf")] * 3
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                corner = apply_matrix(
                    matrix, (sx * half[0], sy * half[1], sz * half[2])
                )
                for axis in range(3):
                    value = corner[axis] + float(at[axis])
                    low[axis] = min(low[axis], value)
                    high[axis] = max(high[axis], value)
    return (low[0], low[1], low[2]), (high[0], high[1], high[2])


# --------------------------------------------------------------------------
# Primitive meshes
#
# Each returns (positions, normals, indices) in a unit-sized, origin-centred
# frame, which `build_part` then scales, rotates and translates. Normals are
# per-vertex and generated with the geometry rather than derived afterwards:
# a flat-shaded box needs four vertices per face, and recovering that from a
# shared-vertex mesh means guessing where the creases were.
# --------------------------------------------------------------------------


def _box() -> tuple[list[Vec3], list[Vec3], list[int]]:
    faces = (
        ((0, 0, 1), ((-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5))),
        ((0, 0, -1), ((0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5))),
        ((1, 0, 0), ((0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5))),
        ((-1, 0, 0), ((-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5))),
        ((0, 1, 0), ((-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5))),
        ((0, -1, 0), ((-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5))),
    )
    positions: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []
    for normal, corners in faces:
        base = len(positions)
        positions.extend(corners)
        normals.extend([tuple(float(v) for v in normal)] * 4)  # type: ignore[arg-type]
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return positions, normals, indices


def _cylinder(segments: int) -> tuple[list[Vec3], list[Vec3], list[int]]:
    positions: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []

    # Side wall: its own vertices, so the wall's outward normals do not get
    # averaged with the caps' and round off the rim.
    for step in range(segments + 1):
        angle = 2.0 * math.pi * step / segments
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        positions.append((0.5 * cos_a, -0.5, 0.5 * sin_a))
        positions.append((0.5 * cos_a, 0.5, 0.5 * sin_a))
        normals.extend([(cos_a, 0.0, sin_a), (cos_a, 0.0, sin_a)])
    for step in range(segments):
        base = step * 2
        indices.extend([base, base + 2, base + 3, base, base + 3, base + 1])

    for sign, normal in ((0.5, (0.0, 1.0, 0.0)), (-0.5, (0.0, -1.0, 0.0))):
        centre = len(positions)
        positions.append((0.0, sign, 0.0))
        normals.append(normal)
        for step in range(segments + 1):
            angle = 2.0 * math.pi * step / segments
            positions.append((0.5 * math.cos(angle), sign, 0.5 * math.sin(angle)))
            normals.append(normal)
        for step in range(segments):
            first, second = centre + 1 + step, centre + 2 + step
            indices.extend(
                [centre, second, first] if sign > 0 else [centre, first, second]
            )
    return positions, normals, indices


def _cone(segments: int) -> tuple[list[Vec3], list[Vec3], list[int]]:
    positions: list[Vec3] = [(0.0, 0.5, 0.0)]
    normals: list[Vec3] = [(0.0, 1.0, 0.0)]
    indices: list[int] = []
    for step in range(segments + 1):
        angle = 2.0 * math.pi * step / segments
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        positions.append((0.5 * cos_a, -0.5, 0.5 * sin_a))
        # Slant normal for a unit cone: the side rises one unit over a half-
        # unit radius, so the vertical component is 0.5 before normalising.
        length = math.sqrt(1.0 + 0.25)
        normals.append((cos_a / length, 0.5 / length, sin_a / length))
    for step in range(segments):
        indices.extend([0, step + 2, step + 1])

    centre = len(positions)
    positions.append((0.0, -0.5, 0.0))
    normals.append((0.0, -1.0, 0.0))
    for step in range(segments + 1):
        angle = 2.0 * math.pi * step / segments
        positions.append((0.5 * math.cos(angle), -0.5, 0.5 * math.sin(angle)))
        normals.append((0.0, -1.0, 0.0))
    for step in range(segments):
        indices.extend([centre, centre + 1 + step, centre + 2 + step])
    return positions, normals, indices


def _sphere(segments: int) -> tuple[list[Vec3], list[Vec3], list[int]]:
    rings = max(3, segments // 2)
    positions: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        for step in range(segments + 1):
            theta = 2.0 * math.pi * step / segments
            nx = math.sin(phi) * math.cos(theta)
            ny = math.cos(phi)
            nz = math.sin(phi) * math.sin(theta)
            positions.append((0.5 * nx, 0.5 * ny, 0.5 * nz))
            normals.append((nx, ny, nz))
    stride = segments + 1
    for ring in range(rings):
        for step in range(segments):
            a = ring * stride + step
            b = a + stride
            indices.extend([a, b, b + 1, a, b + 1, a + 1])
    return positions, normals, indices


def _torus(segments: int, tube_ratio: float = 0.3) -> tuple[list[Vec3], list[Vec3], list[int]]:
    tube_segments = max(3, segments // 2)
    ring_radius = 0.5 - 0.5 * tube_ratio
    tube_radius = 0.5 * tube_ratio
    positions: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []
    for ring in range(segments + 1):
        theta = 2.0 * math.pi * ring / segments
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        for step in range(tube_segments + 1):
            phi = 2.0 * math.pi * step / tube_segments
            cos_p, sin_p = math.cos(phi), math.sin(phi)
            positions.append((
                (ring_radius + tube_radius * cos_p) * cos_t,
                tube_radius * sin_p,
                (ring_radius + tube_radius * cos_p) * sin_t,
            ))
            normals.append((cos_p * cos_t, sin_p, cos_p * sin_t))
    stride = tube_segments + 1
    for ring in range(segments):
        for step in range(tube_segments):
            a = ring * stride + step
            b = a + stride
            indices.extend([a, b, b + 1, a, b + 1, a + 1])
    return positions, normals, indices


def _lathe(profile: Sequence[Sequence[float]], segments: int
           ) -> tuple[list[Vec3], list[Vec3], list[int]]:
    """Revolve a `(radius, height)` profile about Y.

    Carries the shapes — bottles, blades, mouldings, turned legs — that
    would otherwise each need a bespoke primitive. Profile coordinates are
    in the same unit frame as everything else and are scaled by `size`.
    """

    points = [(float(r), float(h)) for r, h in profile]
    if len(points) < 2:
        raise ValueError("a lathe profile needs at least two points")

    positions: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []
    for step in range(segments + 1):
        angle = 2.0 * math.pi * step / segments
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        for index, (radius, height) in enumerate(points):
            positions.append((radius * cos_a, height, radius * sin_a))
            # Profile tangent, rotated a quarter turn into an outward normal.
            previous = points[max(0, index - 1)]
            following = points[min(len(points) - 1, index + 1)]
            dr = following[0] - previous[0]
            dh = following[1] - previous[1]
            length = math.hypot(dr, dh) or 1.0
            nr, ny = dh / length, -dr / length
            normals.append((nr * cos_a, ny, nr * sin_a))
    stride = len(points)
    for step in range(segments):
        for index in range(stride - 1):
            a = step * stride + index
            b = a + stride
            indices.extend([a, b, b + 1, a, b + 1, a + 1])
    return positions, normals, indices


def _extrude(profile: Sequence[Sequence[float]], depth: float = 1.0
             ) -> tuple[list[Vec3], list[Vec3], list[int]]:
    """Extrude a closed 2D `(x, y)` outline along Z, with flat caps."""

    outline = [(float(x), float(y)) for x, y in profile]
    if len(outline) < 3:
        raise ValueError("an extrude profile needs at least three points")

    half = depth / 2.0
    positions: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []

    count = len(outline)
    for index in range(count):
        x0, y0 = outline[index]
        x1, y1 = outline[(index + 1) % count]
        edge_x, edge_y = x1 - x0, y1 - y0
        length = math.hypot(edge_x, edge_y) or 1.0
        normal = (edge_y / length, -edge_x / length, 0.0)
        base = len(positions)
        positions.extend([
            (x0, y0, -half), (x1, y1, -half), (x1, y1, half), (x0, y0, half),
        ])
        normals.extend([normal] * 4)
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    # Fan-triangulated caps: correct for the convex outlines a hard-surface
    # spec uses, and a concave one shows up immediately in the review sheet
    # rather than silently producing a filled notch.
    for sign, normal in ((half, (0.0, 0.0, 1.0)), (-half, (0.0, 0.0, -1.0))):
        base = len(positions)
        for x, y in outline:
            positions.append((x, y, sign))
            normals.append(normal)
        for index in range(1, count - 1):
            triangle = (base, base + index, base + index + 1)
            indices.extend(triangle if sign > 0 else tuple(reversed(triangle)))
    return positions, normals, indices


def build_part(part: dict[str, Any]) -> tuple[list[Vec3], list[Vec3], list[int]]:
    """Evaluate one spec part into world-space positions, normals and indices."""

    kind = part["kind"]
    segments = max(3, int(part.get("segments") or 16))
    profile = part.get("profile")

    if kind == "box":
        positions, normals, indices = _box()
    elif kind == "cylinder":
        positions, normals, indices = _cylinder(segments)
    elif kind == "cone":
        positions, normals, indices = _cone(segments)
    elif kind == "sphere":
        positions, normals, indices = _sphere(segments)
    elif kind == "torus":
        positions, normals, indices = _torus(segments)
    elif kind == "lathe":
        positions, normals, indices = _lathe(profile or ((0.5, -0.5), (0.5, 0.5)), segments)
    elif kind == "extrude":
        positions, normals, indices = _extrude(
            profile or ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))
        )
    else:
        raise ValueError(f"unknown primitive kind {kind!r}")

    size = part["size"]
    at = part["at"]
    matrix = euler_matrix(part.get("rotation") or (0.0, 0.0, 0.0))

    placed: list[Vec3] = []
    for x, y, z in positions:
        scaled = (x * size[0], y * size[1], z * size[2])
        rx, ry, rz = apply_matrix(matrix, scaled)
        placed.append((rx + at[0], ry + at[1], rz + at[2]))

    # Normals transform by the inverse transpose, which for a non-uniform
    # scale is *not* the same matrix — using the forward one tilts every
    # normal on any part that is not scaled equally in all three axes, and
    # the result is lighting that looks like a modelling error.
    inverse_scale = tuple(1.0 / value if value else 0.0 for value in size)
    turned: list[Vec3] = []
    for nx, ny, nz in normals:
        sx = nx * inverse_scale[0]
        sy = ny * inverse_scale[1]
        sz = nz * inverse_scale[2]
        rx, ry, rz = apply_matrix(matrix, (sx, sy, sz))
        length = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        turned.append((rx / length, ry / length, rz / length))

    return placed, turned, indices


# --------------------------------------------------------------------------
# GLB assembly
# --------------------------------------------------------------------------


def _pad(data: bytearray, alignment: int = 4, fill: int = 0) -> None:
    while len(data) % alignment:
        data.append(fill)


def write_spec_glb(spec: dict[str, Any], out_path: str | Path) -> str:
    """Write `spec` as a `.glb` and return the path.

    One glTF mesh per spec part, each as its own node **keeping the part's
    id as the node name**. That is the property a generated mesh cannot
    offer: a wheel arrives as a node called `wheel-fl`, so gameplay can spin
    it after import instead of the whole vehicle being one fused body.
    """

    parts = spec["parts"]
    if not parts:
        raise ValueError("a spec needs at least one part")

    materials_in = spec.get("materials") or {}
    material_index: dict[str, int] = {}
    materials: list[dict[str, Any]] = []

    buffer = bytearray()
    views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    def add_view(payload: bytes, target: int | None = None) -> int:
        _pad(buffer)                     # accessor offsets must stay aligned
        offset = len(buffer)
        buffer.extend(payload)
        view: dict[str, Any] = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(payload),
        }
        if target is not None:
            view["target"] = target
        views.append(view)
        return len(views) - 1

    for part in parts:
        positions, normals, indices = build_part(part)

        position_view = add_view(
            b"".join(struct.pack("<3f", *point) for point in positions), 34962
        )
        normal_view = add_view(
            b"".join(struct.pack("<3f", *vector) for vector in normals), 34962
        )
        index_view = add_view(
            b"".join(struct.pack("<I", value) for value in indices), 34963
        )

        low = [min(point[axis] for point in positions) for axis in range(3)]
        high = [max(point[axis] for point in positions) for axis in range(3)]

        # POSITION requires min/max: a viewer uses them to frame the scene,
        # and a validator rejects the file without them.
        accessors.append({
            "bufferView": position_view,
            "componentType": _FLOAT,
            "count": len(positions),
            "type": "VEC3",
            "min": [round(value, 6) for value in low],
            "max": [round(value, 6) for value in high],
        })
        accessors.append({
            "bufferView": normal_view,
            "componentType": _FLOAT,
            "count": len(normals),
            "type": "VEC3",
        })
        accessors.append({
            "bufferView": index_view,
            "componentType": _UNSIGNED_INT,
            "count": len(indices),
            "type": "SCALAR",
        })
        position_accessor = len(accessors) - 3
        normal_accessor = len(accessors) - 2
        index_accessor = len(accessors) - 1

        name = str(part.get("material") or "default")
        if name not in material_index:
            described = {**DEFAULT_MATERIAL, **(materials_in.get(name) or {})}
            colour = list(described.get("baseColor", DEFAULT_MATERIAL["baseColor"]))
            if len(colour) == 3:
                colour.append(1.0)
            materials.append({
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [float(value) for value in colour],
                    "metallicFactor": float(described.get("metallic", 0.0)),
                    "roughnessFactor": float(described.get("roughness", 0.6)),
                },
                "doubleSided": bool(described.get("doubleSided", False)),
            })
            material_index[name] = len(materials) - 1

        meshes.append({
            "name": part["id"],
            "primitives": [{
                "attributes": {
                    "POSITION": position_accessor,
                    "NORMAL": normal_accessor,
                },
                "indices": index_accessor,
                "material": material_index[name],
                "mode": _MODE_TRIANGLES,
            }],
        })
        nodes.append({"name": part["id"], "mesh": len(meshes) - 1})

    document: dict[str, Any] = {
        "asset": {
            "version": "2.0",
            "generator": GENERATOR,
        },
        "scene": 0,
        "scenes": [{
            "name": spec.get("subject") or "asset",
            "nodes": list(range(len(nodes))),
        }],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(buffer)}],
    }
    # The spec is kept inside the file it produced. A GLB whose spec has
    # been lost cannot be corrected by editing a number, which is most of
    # the reason to build assets this way.
    document["extras"] = {
        "gamefactory3a": {
            "spec": spec,
            "forwardAxis": spec.get("forward"),
            "heightMetres": spec.get("height_metres"),
            "units": spec.get("units"),
        }
    }

    json_chunk = bytearray(json.dumps(document, separators=(",", ":")).encode("utf-8"))
    _pad(json_chunk, 4, ord(" "))        # JSON pads with spaces, BIN with zeros
    binary_chunk = bytearray(buffer)
    _pad(binary_chunk, 4, 0)

    total = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    out = bytearray()
    out.extend(struct.pack("<4sII", b"glTF", 2, total))
    out.extend(struct.pack("<I4s", len(json_chunk), b"JSON"))
    out.extend(json_chunk)
    out.extend(struct.pack("<I4s", len(binary_chunk), b"BIN\x00"))
    out.extend(binary_chunk)

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))
    return str(path)
