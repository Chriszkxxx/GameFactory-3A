"""Inspect an exported FBX inside a bpy-capable subprocess."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def inspect_fbx(input_path: str, *, require_mesh: bool = True) -> dict:
    """Import one FBX and report structural animation information."""
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(Path(input_path).resolve()),
        anim_offset=0.0,
    )
    meshes = [
        obj for obj in bpy.context.scene.objects if obj.type == "MESH"
    ]
    armatures = [
        obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"
    ]
    actions = list(bpy.data.actions)
    keyframes = sorted(
        {
            int(round(point.co.x))
            for action in actions
            for curve in action.fcurves
            for point in curve.keyframe_points
        }
    )
    return {
        "mesh_count": len(meshes),
        "armature_count": len(armatures),
        "action_count": len(actions),
        "keyframe_count": len(keyframes),
        "frame_range": (
            [keyframes[0], keyframes[-1]] if keyframes else None
        ),
        "fps": int(bpy.context.scene.render.fps),
        "valid": bool(
            (meshes or not require_mesh) and armatures and actions and keyframes
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--allow-no-mesh",
        action="store_true",
        help="Validate an animation-only FBX containing no mesh.",
    )
    args = parser.parse_args()
    report = inspect_fbx(args.input, require_mesh=not args.allow_no_mesh)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["valid"]:
        raise RuntimeError(f"FBX failed structural validation: {report}")


if __name__ == "__main__":
    main()
