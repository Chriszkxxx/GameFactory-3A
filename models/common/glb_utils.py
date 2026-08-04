"""
models/common/glb_utils.py

Dependency-free inspection of binary glTF (`.glb`) buffers.

Why this exists instead of `trimesh.load(...)`: the API wrappers must report the
triangle count of what they just paid for (`api_model_require.md` R9.8), and
that number has to be available on a CPU-only box with nothing but the stdlib
installed. Parsing the JSON chunk of a GLB is enough for counting.

Nothing here loads geometry — no vertex data is decoded, only accessor counts.

Usage:
    from models.common.glb_utils import glb_summary
    info = glb_summary(open("model.glb", "rb").read())
    print(info["triangles"], info["materials"])
"""
from __future__ import annotations

import json
import struct
from typing import Any, Optional

GLB_MAGIC = b"glTF"

#: glTF primitive mode 4 == TRIANGLES. Only triangle primitives are counted.
_MODE_TRIANGLES = 4


class GLBParseError(ValueError):
    """The buffer is not a GLB we can read."""


def is_glb(data: bytes) -> bool:
    """True when `data` starts with the 12-byte GLB header."""
    return len(data) >= 12 and data[:4] == GLB_MAGIC


def glb_json_chunk(data: bytes) -> dict[str, Any]:
    """
    Return the parsed JSON chunk of a GLB.

    Args:
        data: Whole `.glb` file content.

    Returns:
        The glTF document as a dict.

    Raises:
        GLBParseError: bad magic, truncated file, or a missing JSON chunk.
    """
    if not is_glb(data):
        raise GLBParseError(
            f"not a GLB: expected magic {GLB_MAGIC!r}, got {data[:4]!r}"
        )
    if len(data) < 20:
        raise GLBParseError(f"GLB truncated: {len(data)} bytes")

    _magic, version, total_len = struct.unpack_from("<4sII", data, 0)
    if total_len > len(data):
        raise GLBParseError(
            f"GLB header claims {total_len} bytes, buffer holds {len(data)}"
        )

    offset = 12
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_len]
        offset += chunk_len
        if chunk_type == b"JSON":
            try:
                return json.loads(chunk.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise GLBParseError(f"GLB JSON chunk is not valid JSON: {e}") from e
    raise GLBParseError(f"GLB (version {version}) has no JSON chunk")


def glb_triangle_count(data: bytes) -> Optional[int]:
    """
    Triangle count of a GLB, or None when it cannot be determined.

    Counts every triangle-mode primitive of every mesh once, i.e. the *asset's*
    triangle budget, not the per-instance count after node duplication.

    Returns:
        int triangles, or None if the JSON chunk is unreadable.
    """
    try:
        doc = glb_json_chunk(data)
    except GLBParseError:
        return None

    accessors = doc.get("accessors", [])
    total = 0
    for mesh in doc.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if prim.get("mode", _MODE_TRIANGLES) != _MODE_TRIANGLES:
                continue
            idx = prim.get("indices")
            if idx is not None and idx < len(accessors):
                count = accessors[idx].get("count", 0)
            else:
                pos = prim.get("attributes", {}).get("POSITION")
                count = accessors[pos].get("count", 0) if pos is not None and pos < len(accessors) else 0
            total += count // 3
    return total


def glb_summary(data: bytes) -> dict[str, Any]:
    """
    Cheap description of a GLB, for logs and `meta.json`.

    Returns:
        dict with keys:
            bytes (int)            — buffer size
            triangles (int | None) — see `glb_triangle_count`
            meshes, materials, textures, images, nodes (int)
            generator (str | None) — glTF `asset.generator`
            error (str)            — present only when the JSON chunk is unreadable
    """
    out: dict[str, Any] = {"bytes": len(data)}
    try:
        doc = glb_json_chunk(data)
    except GLBParseError as e:
        out.update({"triangles": None, "error": str(e)})
        return out

    out.update({
        "triangles": glb_triangle_count(data),
        "meshes": len(doc.get("meshes", [])),
        "materials": len(doc.get("materials", [])),
        "textures": len(doc.get("textures", [])),
        "images": len(doc.get("images", [])),
        "nodes": len(doc.get("nodes", [])),
        "generator": (doc.get("asset") or {}).get("generator"),
    })
    return out
