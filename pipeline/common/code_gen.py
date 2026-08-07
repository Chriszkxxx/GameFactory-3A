"""Task-neutral helpers for outer-Agent code-generation pipelines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pipeline.common import paths
from pipeline.common.artifacts import (
    is_relative_to,
    resolve_repo_path,
)


def mapping_list(
    value: Any,
    name: str,
) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes)) or not isinstance(
        value,
        Sequence,
    ):
        raise TypeError(f"{name} must be a sequence")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TypeError(
                f"{name}[{index}] must be an object"
            )
        result.append(dict(item))
    return result


def string_list(
    value: Any,
    name: str,
) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(
        value,
        Sequence,
    ):
        raise TypeError(f"{name} must be a sequence")
    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def resolve_examples(
    task: Mapping[str, Any],
) -> list[Path]:
    raw_examples = (
        task.get("example_paths")
        or task.get("examples")
        or []
    )
    if isinstance(raw_examples, (str, Path, Mapping)):
        raw_examples = [raw_examples]
    if not isinstance(raw_examples, Sequence):
        raise TypeError("example_paths must be a sequence")
    result: list[Path] = []
    for item in raw_examples:
        value = (
            item.get("path")
            if isinstance(item, Mapping)
            else item
        )
        result.append(
            resolve_repo_path(
                str(value or ""),
                "example path",
                must_exist=True,
            )
        )
    return result


def repair_payload(
    task: Mapping[str, Any],
    mode: str,
) -> tuple[dict[str, Any], int]:
    if mode == "generate":
        return {}, 0
    raw_repair = task.get("repair")
    if not isinstance(raw_repair, Mapping):
        raise TypeError(
            "repair must be an object in repair mode"
        )
    repair = dict(raw_repair)
    attempt = int(repair.get("attempt") or 0)
    max_attempts = int(repair.get("max_attempts") or 0)
    if attempt <= 0 or max_attempts <= 0:
        raise ValueError(
            "repair attempt and max_attempts must be positive"
        )
    if attempt > max_attempts:
        raise ValueError(
            "repair attempt must not exceed max_attempts"
        )
    failures = mapping_list(
        repair.get("failures", []),
        "repair.failures",
    )
    if not failures:
        raise ValueError(
            "repair.failures must not be empty"
        )
    previous = repair.get("previous_result")
    if not isinstance(previous, Mapping):
        raise TypeError(
            "repair.previous_result must be an object"
        )
    repair["attempt"] = attempt
    repair["max_attempts"] = max_attempts
    repair["failures"] = failures
    repair["previous_result"] = dict(previous)
    return repair, attempt


def validate_boundaries(
    workspace: Path,
    read_only_paths: Sequence[Path],
) -> None:
    for reference in read_only_paths:
        resolved = reference.resolve(strict=False)
        if (
            is_relative_to(workspace, resolved)
            or is_relative_to(resolved, workspace)
        ):
            raise ValueError(
                "workspace and read-only paths must not overlap: "
                f"{resolved}"
            )


def validate_engine_context_root(
    engine_context_root: str | Path,
) -> Path:
    root = Path(engine_context_root)
    if not root.is_dir():
        raise FileNotFoundError(
            "Engine Context directory was not found: "
            f"{root}"
        )
    if not any(
        path.is_file()
        for path in root.glob("*_api.md")
    ):
        raise FileNotFoundError(
            "Engine Context directory contains no API references: "
            f"{root}"
        )
    return root


def select_task(
    tasks_path: str | Path,
    *,
    game_id: str | None,
    task_id: str | None,
    task_name: str,
) -> dict[str, Any]:
    matches = [
        dict(task)
        for task, _ in paths.iter_tasks(
            tasks_path,
            game_filter=game_id,
        )
        if not task_id
        or str(task.get("task_id") or "") == task_id
    ]
    if not matches:
        raise ValueError(
            f"No matching {task_name} task was found"
        )
    if len(matches) > 1:
        raise ValueError(
            f"{task_name} prepare handles one task at a time; "
            "pass --task-id"
        )
    return matches[0]
