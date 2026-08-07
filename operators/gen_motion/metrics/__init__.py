"""Read-only structural metrics for motion retarget artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_EXPECTED_CHAINS = {"spine", "left_arm", "right_arm", "left_leg", "right_leg"}


def _artifact_ok(value: str | None) -> bool:
    if value is None:
        return False
    path = Path(value)
    return path.is_file() and path.stat().st_size > 0


def _read_json(path_like: str | None) -> dict[str, Any] | None:
    if not _artifact_ok(path_like):
        return None
    try:
        value = json.loads(
            Path(str(path_like)).read_text(encoding="utf-8-sig")
        )
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def evaluate(result: dict, task: dict) -> dict[str, Any]:
    """Evaluate existing retarget artifacts without invoking generation."""
    mapping = _read_json(result.get("mapping_path"))
    info = _read_json(result.get("retarget_info_path"))
    export_anim_only = bool(task.get("export_anim_only", True))

    artifacts = {
        "retargeted_fbx": _artifact_ok(result.get("retargeted_fbx_path")),
        "anim_only_fbx": (
            _artifact_ok(result.get("anim_only_fbx_path"))
            if export_anim_only
            else not _artifact_ok(result.get("anim_only_fbx_path"))
        ),
        "mapping": mapping is not None,
        "retarget_info": info is not None,
    }

    bone_map = mapping.get("bone_map", {}) if mapping else {}
    chains = mapping.get("retarget_chains", {}) if mapping else {}
    source_count = int((info or {}).get("source_bone_count") or 0)
    target_count = int((info or {}).get("target_bone_count") or 0)
    mapped_source = len(set(bone_map))
    mapped_target = len(set(bone_map.values())) if bone_map else 0
    present_chains = _EXPECTED_CHAINS.intersection(chains)

    source_range = (info or {}).get("source_frame_range")
    output_range = (info or {}).get("output_frame_range")
    timing_preserved = (
        isinstance(source_range, list)
        and len(source_range) == 2
        and source_range == output_range
    )

    return {
        "task_id": result.get("task_id"),
        "artifact_valid": all(artifacts.values()),
        "artifacts": artifacts,
        "mapping_valid": bool(bone_map),
        "mapped_bone_count": mapped_source,
        "source_bone_coverage": (
            round(mapped_source / source_count, 4) if source_count else None
        ),
        "target_bone_coverage": (
            round(mapped_target / target_count, 4) if target_count else None
        ),
        "required_chain_coverage": round(
            len(present_chains) / len(_EXPECTED_CHAINS), 4
        ),
        "missing_chains": sorted(_EXPECTED_CHAINS - present_chains),
        "timing_preserved": timing_preserved,
        "fps": (info or {}).get("fps"),
        "anim_only_available": _artifact_ok(result.get("anim_only_fbx_path")),
    }


__all__ = ["evaluate"]
