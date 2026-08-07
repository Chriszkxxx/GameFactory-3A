"""Mechanic artifact validation and workspace finalization."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from pipeline.code_gen.gen_mechanic.contracts import (
    validate_mechanic_contract,
)
from pipeline.common.artifacts import read_json
from pipeline.common.finalize import finalize_workspace


_UE_ENGINE_IDS = {
    "ue",
    "ue5",
    "unreal",
    "unreal_engine",
    "unrealengine",
}
_UE_SOURCE_SUFFIXES = {
    ".h",
    ".hh",
    ".hpp",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".cs",
    ".ini",
    ".uplugin",
    ".uproject",
}
_UE_UI_PATTERNS = (
    ("AHUD", re.compile(r"\bAHUD\b")),
    ("DrawHUD", re.compile(r"\bDrawHUD\b")),
    ("UUserWidget", re.compile(r"\bUUserWidget\b")),
    (
        "Engine/Canvas.h",
        re.compile(r"Engine[\\/]Canvas\.h"),
    ),
    (
        "GameFramework/HUD.h",
        re.compile(r"GameFramework[\\/]HUD\.h"),
    ),
    ("HUDClass", re.compile(r"\bHUDClass\b")),
    ("Canvas", re.compile(r"\bCanvas\b")),
    ("UMG", re.compile(r"\bUMG\b")),
    ("Slate", re.compile(r"\bSlate(?:Core)?\b")),
)


def _has_files(path: Path) -> bool:
    return path.is_dir() and any(
        item.is_file()
        for item in path.rglob("*")
    )


def scan_ue_ui_contamination(
    workspace: Path,
    current_task_files: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, list[str]]:
    violations: list[str] = []
    for relative_path in current_task_files:
        path = workspace / relative_path
        if (
            not path.is_file()
            or path.suffix.lower() not in _UE_SOURCE_SUFFIXES
        ):
            continue
        try:
            source = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError as exc:
            violations.append(
                "Unable to inspect generated Mechanic source "
                f"{relative_path}: {exc}"
            )
            continue
        matches = [
            name
            for name, pattern in _UE_UI_PATTERNS
            if pattern.search(source)
        ]
        if matches:
            violations.append(
                "UE Mechanic source contains forbidden UI "
                f"implementation in {relative_path}: "
                + ", ".join(matches)
            )
    return not violations, violations


def required_artifact_checks(
    workspace: Path,
    required: Sequence[str],
    current_task_files: Mapping[str, Mapping[str, Any]],
    *,
    engine: str,
    gameplay_module_name: str,
) -> tuple[dict[str, bool | None], list[str], list[str]]:
    checks: dict[str, bool | None] = {}
    errors: list[str] = []
    warnings: list[str] = []
    for artifact in required:
        if artifact == "project_file":
            checks[artifact] = _has_files(
                workspace / "project"
            )
        elif artifact == "plugin_dir":
            checks[artifact] = _has_files(
                workspace / "generated_plugin"
            )
        elif artifact == "launch_script":
            checks[artifact] = any(
                path.is_file()
                for path in workspace.glob("launch*")
            )
        elif artifact == "demo_outputs_dir":
            checks[artifact] = (
                workspace / "demo_outputs"
            ).is_dir()
        else:
            checks[artifact] = None
            warnings.append(
                "Finalize has no engine-neutral check for "
                f"required artifact {artifact!r}"
            )
    for artifact, passed in checks.items():
        if passed is False:
            errors.append(
                f"Required Mechanic artifact is missing: {artifact}"
            )

    generated_tests = [
        relative_path
        for relative_path in current_task_files
        if any(
            "test" in part.lower()
            for part in PurePosixPath(relative_path).parts
        )
    ]
    checks["generated_test_source"] = bool(generated_tests)
    if not generated_tests:
        errors.append(
            "No generated Mechanic test source was found"
        )

    contract_ok, contract_errors = (
        validate_mechanic_contract(
            workspace,
            gameplay_module_name,
        )
    )
    checks["mechanic_contract"] = contract_ok
    errors.extend(contract_errors)

    if engine.strip().lower() in _UE_ENGINE_IDS:
        ui_free, contamination_errors = (
            scan_ue_ui_contamination(
                workspace,
                current_task_files,
            )
        )
        checks["ue_ui_free_source"] = ui_free
        errors.extend(contamination_errors)
    else:
        checks["ue_ui_free_source"] = None
    return checks, errors, warnings


def finalize(
    packet_path: str | Path,
    *,
    summary: str = "",
) -> dict[str, Any]:
    """Finalize one directly edited Mechanic workspace."""
    packet = read_json(
        packet_path,
        "Prepared Mechanic task packet",
    )
    engine = str(packet.get("engine") or "")
    gameplay_module_name = str(
        packet.get("gameplay_module_name") or ""
    )

    def artifact_checker(
        workspace: Path,
        required: Sequence[str],
        current_task_files: Mapping[str, Mapping[str, Any]],
    ) -> tuple[
        dict[str, bool | None],
        list[str],
        list[str],
    ]:
        return required_artifact_checks(
            workspace,
            required,
            current_task_files,
            engine=engine,
            gameplay_module_name=gameplay_module_name,
        )

    return finalize_workspace(
        packet_path,
        summary=summary,
        artifact_checker=artifact_checker,
    )
