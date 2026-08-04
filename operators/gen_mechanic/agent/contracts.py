"""JSON-serializable request and result contracts for Mechanic Agents."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


REQUEST_MODES = ("generate", "repair")
RESULT_STATUSES = (
    "completed",
    "failed",
    "cancelled",
    "timed_out",
)


def _mapping(
    value: Any,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return dict(value)


def _nonempty_string(
    value: Any,
    name: str,
) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


def _string_list(
    value: Any,
    name: str,
) -> list[str]:
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence, not a string")
    if not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return [
        _nonempty_string(item, f"{name} item")
        for item in value
    ]


def _mapping_list(
    value: Any,
    name: str,
) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence, not a string")
    if not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence")
    return [
        _mapping(item, f"{name} item")
        for item in value
    ]


def _is_relative_to(
    path: Path,
    root: Path,
) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolved_path(
    value: Any,
    name: str,
) -> Path:
    return Path(
        _nonempty_string(value, name)
    ).expanduser().resolve(strict=False)


def resolve_workspace_file(
    workspace: str | Path,
    relative_path: str,
) -> Path:
    root = Path(workspace).expanduser().resolve(strict=False)
    relative = Path(
        _nonempty_string(
            relative_path,
            "generated file path",
        )
    )
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(
            "generated file paths must be relative to the workspace"
        )
    target = (root / relative).resolve(strict=False)
    if not _is_relative_to(target, root):
        raise ValueError(
            f"generated file escapes the workspace: {relative_path}"
        )
    return target


def _readonly_reference(
    value: Any,
    name: str,
    *,
    require_path: bool = False,
    require_file: bool = False,
) -> dict[str, Any]:
    reference = _mapping(value, name)
    path_text = str(
        reference.get("path") or ""
    ).strip()
    content = str(
        reference.get("content") or ""
    )
    if require_path and not path_text:
        raise ValueError(f"{name}.path must not be empty")
    if not path_text and not content.strip():
        raise ValueError(
            f"{name} must provide a path or content"
        )
    resolved_path = (
        _resolved_path(
            path_text,
            f"{name}.path",
        )
        if path_text
        else None
    )
    if resolved_path is not None and not resolved_path.exists():
        raise ValueError(
            f"{name}.path does not exist: {resolved_path}"
        )
    if require_file and (
        resolved_path is None
        or not resolved_path.is_file()
        or resolved_path.stat().st_size == 0
    ):
        raise ValueError(
            f"{name}.path must be a non-empty file"
        )
    reference["path"] = str(resolved_path or "")
    reference["content"] = content
    if reference.get("read_only") is not True:
        raise ValueError(f"{name}.read_only must be true")
    return reference


def _positive_number_or_none(
    value: Any,
    name: str,
) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be numeric or null") from exc
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _positive_integer_or_none(
    value: Any,
    name: str,
) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer or null")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be an integer or null") from exc
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _ensure_json_serializable(
    value: Any,
    name: str,
) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"{name} must be JSON-serializable: {exc}"
        ) from exc


def validate_agent_request(
    request: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize one `model.run(request)` input."""
    normalized = copy.deepcopy(
        _mapping(request, "request")
    )
    normalized["request_id"] = _nonempty_string(
        normalized.get("request_id"),
        "request_id",
    )
    mode = _nonempty_string(
        normalized.get("mode"),
        "mode",
    ).lower()
    if mode not in REQUEST_MODES:
        raise ValueError(
            f"mode must be one of {REQUEST_MODES}"
        )
    normalized["mode"] = mode

    workspace = _resolved_path(
        normalized.get("workspace"),
        "workspace",
    )
    normalized["workspace"] = str(workspace)
    normalized["system_prompt"] = _nonempty_string(
        normalized.get("system_prompt"),
        "system_prompt",
    )
    normalized["task_prompt"] = _nonempty_string(
        normalized.get("task_prompt"),
        "task_prompt",
    )
    repair_prompt = str(
        normalized.get("repair_prompt") or ""
    ).strip()
    if mode == "repair" and not repair_prompt:
        raise ValueError(
            "repair_prompt is required in repair mode"
        )
    normalized["repair_prompt"] = repair_prompt

    context = _mapping(
        normalized.get("context"),
        "context",
    )
    context["task"] = _mapping(
        context.get("task"),
        "context.task",
    )
    context["project_name"] = _nonempty_string(
        context.get("project_name"),
        "context.project_name",
    )
    context["gameplay_module_name"] = _nonempty_string(
        context.get("gameplay_module_name"),
        "context.gameplay_module_name",
    )
    context["general_requirement"] = str(
        context.get("general_requirement") or ""
    )
    context["requirement"] = _nonempty_string(
        context.get("requirement"),
        "context.requirement",
    )
    context["acceptance_criteria"] = _string_list(
        context.get("acceptance_criteria", []),
        "context.acceptance_criteria",
    )
    context["asset_sources"] = _mapping_list(
        context.get("asset_sources", []),
        "context.asset_sources",
    )
    context["motion_sources"] = _mapping_list(
        context.get("motion_sources", []),
        "context.motion_sources",
    )
    context["engine"] = _nonempty_string(
        context.get("engine"),
        "context.engine",
    )
    context["engine_api_reference"] = (
        _readonly_reference(
            context.get("engine_api_reference"),
            "context.engine_api_reference",
            require_path=True,
            require_file=True,
        )
    )
    context["skill"] = _readonly_reference(
        context.get("skill"),
        "context.skill",
        require_path=True,
        require_file=True,
    )
    examples = _mapping_list(
        context.get("examples", []),
        "context.examples",
    )
    context["examples"] = [
        _readonly_reference(
            example,
            f"context.examples[{index}]",
            require_path=True,
        )
        for index, example in enumerate(examples)
    ]
    normalized["context"] = context

    constraints = _mapping(
        normalized.get("constraints"),
        "constraints",
    )
    allowed_write_roots = [
        _resolved_path(
            item,
            "constraints.allowed_write_roots item",
        )
        for item in _string_list(
            constraints.get("allowed_write_roots", []),
            "constraints.allowed_write_roots",
        )
    ]
    if not allowed_write_roots:
        raise ValueError(
            "constraints.allowed_write_roots must not be empty"
        )
    if not any(
        _is_relative_to(workspace, root)
        for root in allowed_write_roots
    ):
        raise ValueError(
            "workspace must be inside an allowed write root"
        )
    constraints["allowed_write_roots"] = [
        str(root)
        for root in allowed_write_roots
    ]
    read_only_paths = [
        _resolved_path(
            item,
            "constraints.read_only_paths item",
        )
        for item in _string_list(
            constraints.get("read_only_paths", []),
            "constraints.read_only_paths",
        )
    ]
    reference_paths = [
        Path(context["engine_api_reference"]["path"]),
        Path(context["skill"]["path"]),
        *[
            Path(example["path"])
            for example in context["examples"]
        ],
    ]
    missing_read_only = [
        str(reference)
        for reference in reference_paths
        if not any(
            _is_relative_to(reference, root)
            for root in read_only_paths
        )
    ]
    if missing_read_only:
        raise ValueError(
            "reference paths must be covered by "
            "constraints.read_only_paths: "
            + ", ".join(missing_read_only)
        )
    if any(
        _is_relative_to(workspace, root)
        or _is_relative_to(root, workspace)
        for root in read_only_paths
    ):
        raise ValueError(
            "workspace and read-only paths must not overlap"
        )
    constraints["read_only_paths"] = [
        str(path)
        for path in read_only_paths
    ]
    if constraints.get("agent_may_execute_tests") is not False:
        raise ValueError(
            "constraints.agent_may_execute_tests must be false"
        )
    if (
        constraints.get(
            "agent_may_declare_benchmark_success"
        )
        is not False
    ):
        raise ValueError(
            "constraints.agent_may_declare_benchmark_success "
            "must be false"
        )
    normalized["constraints"] = constraints

    limits = _mapping(
        normalized.get("limits", {}),
        "limits",
    )
    limits["timeout_sec"] = _positive_number_or_none(
        limits.get("timeout_sec"),
        "limits.timeout_sec",
    )
    limits["max_turns"] = _positive_integer_or_none(
        limits.get("max_turns"),
        "limits.max_turns",
    )
    normalized["limits"] = limits

    repair = _mapping(
        normalized.get("repair", {}),
        "repair",
    )
    if mode == "repair":
        attempt = _positive_integer_or_none(
            repair.get("attempt"),
            "repair.attempt",
        )
        max_attempts = _positive_integer_or_none(
            repair.get("max_attempts"),
            "repair.max_attempts",
        )
        if (
            attempt is None
            or max_attempts is None
            or attempt > max_attempts
        ):
            raise ValueError(
                "repair attempt must be within max_attempts"
            )
        failures = _mapping_list(
            repair.get("failures", []),
            "repair.failures",
        )
        if not failures:
            raise ValueError(
                "repair.failures must not be empty in repair mode"
            )
        repair["attempt"] = attempt
        repair["max_attempts"] = max_attempts
        repair["failures"] = failures
        repair["previous_result"] = _mapping(
            repair.get("previous_result"),
            "repair.previous_result",
        )
    normalized["repair"] = repair
    normalized["metadata"] = _mapping(
        normalized.get("metadata", {}),
        "metadata",
    )

    _ensure_json_serializable(
        normalized,
        "request",
    )
    return normalized


def validate_agent_result(
    result: Mapping[str, Any],
    *,
    request_id: str,
    workspace: str | Path,
) -> dict[str, Any]:
    """Validate and normalize one `model.run(request)` result."""
    normalized = copy.deepcopy(
        _mapping(result, "result")
    )
    if not isinstance(normalized.get("ok"), bool):
        raise TypeError("result.ok must be a boolean")
    normalized["request_id"] = _nonempty_string(
        normalized.get("request_id"),
        "result.request_id",
    )
    if normalized["request_id"] != request_id:
        raise ValueError(
            "result.request_id does not match the request"
        )
    status = _nonempty_string(
        normalized.get("status"),
        "result.status",
    ).lower()
    if status not in RESULT_STATUSES:
        raise ValueError(
            f"result.status must be one of {RESULT_STATUSES}"
        )
    normalized["status"] = status
    if normalized["ok"] != (status == "completed"):
        raise ValueError(
            "result.ok must be true only for completed status"
        )

    workspace_root = Path(workspace).resolve(strict=False)
    path_groups = {
        "generated_files": True,
        "modified_files": True,
        "deleted_files": False,
    }
    normalized_paths: dict[str, list[str]] = {}
    resolved_groups: dict[str, set[Path]] = {}
    for field, must_exist in path_groups.items():
        values = _string_list(
            normalized.get(field, []),
            f"result.{field}",
        )
        normalized_paths[field] = []
        resolved_groups[field] = set()
        for relative_path in values:
            target = resolve_workspace_file(
                workspace_root,
                relative_path,
            )
            if must_exist and not target.is_file():
                raise ValueError(
                    f"result.{field} file does not exist: "
                    f"{relative_path}"
                )
            if not must_exist and target.exists():
                raise ValueError(
                    f"result.deleted_files path still exists: "
                    f"{relative_path}"
                )
            resolved_groups[field].add(target)
            normalized_paths[field].append(
                target.relative_to(
                    workspace_root
                ).as_posix()
            )
        normalized[field] = normalized_paths[field]
    for left, right in (
        ("generated_files", "modified_files"),
        ("generated_files", "deleted_files"),
        ("modified_files", "deleted_files"),
    ):
        if resolved_groups[left] & resolved_groups[right]:
            raise ValueError(
                f"result file paths overlap between {left} and {right}"
            )

    normalized["diagnostics"] = _mapping_list(
        normalized.get("diagnostics", []),
        "result.diagnostics",
    )
    normalized["warnings"] = _string_list(
        normalized.get("warnings", []),
        "result.warnings",
    )
    normalized["errors"] = _string_list(
        normalized.get("errors", []),
        "result.errors",
    )
    if normalized["ok"] and normalized["errors"]:
        raise ValueError(
            "a completed result must not contain errors"
        )
    if (
        not normalized["ok"]
        and not normalized["errors"]
        and not normalized["diagnostics"]
    ):
        raise ValueError(
            "a failed result must contain errors or diagnostics"
        )
    normalized["transcript"] = _mapping_list(
        normalized.get("transcript", []),
        "result.transcript",
    )
    normalized["usage"] = _mapping(
        normalized.get("usage", {}),
        "result.usage",
    )
    normalized["payload"] = _mapping(
        normalized.get("payload", {}),
        "result.payload",
    )
    _ensure_json_serializable(
        normalized,
        "result",
    )
    return normalized
