"""Prepare and finalize one outer-Agent Generate-Mechanic task."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.common import paths
from pipeline.common.artifacts import (
    identifier,
    is_relative_to,
    json_text,
    read_json,
    read_required_text,
    render_template,
    resolve_repo_path,
)
from pipeline.common.finalize import finalize_workspace
from pipeline.common.prepare import (
    DEFAULT_RESERVED_ROOTS,
    code_gen_stage_dir,
    prepare_workspace,
    resolve_task_workspace,
)


TASK_KIND = "mechanic"
CONTEXT_ROOT = (
    paths.REPO_ROOT
    / "agent_skills"
    / "code_gen"
    / "mechanic"
)
ENGINE_CONTEXT_ROOT = (
    paths.REPO_ROOT
    / "agent_skills"
    / "engine_context"
)
SKILL_PATH = CONTEXT_ROOT / "game_generation.md"
PROMPTS_ROOT = CONTEXT_ROOT / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_ROOT / "system.md"
TASK_PROMPT_PATH = PROMPTS_ROOT / "task.md"
REPAIR_PROMPT_PATH = PROMPTS_ROOT / "repair.md"


def _mapping_list(
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


def _string_list(
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


def _resolve_examples(
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


def _repair_payload(
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
    failures = _mapping_list(
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


def _validate_boundaries(
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


def _has_files(path: Path) -> bool:
    return path.is_dir() and any(
        item.is_file()
        for item in path.rglob("*")
    )


def _required_artifact_checks(
    workspace: Path,
    required: Sequence[str],
    current_task_files: Mapping[str, Mapping[str, Any]],
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
    return checks, errors, warnings


def prepare(
    inp: dict[str, Any],
    *,
    run_id: str = paths.DEFAULT_RUN_ID,
    output_dir: str | None = None,
    default_game_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Compose one Mechanic packet without loading a Model or Operator."""
    if not isinstance(inp, Mapping):
        raise TypeError("Mechanic task must be an object")
    task = dict(inp)
    mode = str(task.get("mode") or "generate").strip().lower()
    if mode not in {"generate", "repair"}:
        raise ValueError(
            "Mechanic task mode must be generate or repair"
        )
    repair, repair_attempt = _repair_payload(task, mode)
    task_id = str(task.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("Mechanic task must contain task_id")
    engine = str(task.get("engine") or "").strip()
    if not engine:
        raise ValueError("Mechanic task must contain engine")

    game_id, workspace, standard_layout = (
        resolve_task_workspace(
            task,
            task_kind=TASK_KIND,
            task_id=task_id,
            run_id=run_id,
            output_dir=output_dir,
            default_game_id=default_game_id,
        )
    )
    project_name = identifier(
        task.get("project_name")
        or f"A3Game_{task_id}",
        "A3Game",
    )
    gameplay_module_name = identifier(
        task.get("gameplay_module_name")
        or f"{project_name}_Gameplay",
        "GeneratedGameplay",
    )
    requirement_path = resolve_repo_path(
        str(task.get("requirement_path") or ""),
        "requirement_path",
        require_file=True,
    )
    requirement = read_required_text(
        requirement_path,
        "Mechanic requirement",
    )
    general_requirement_path = (
        paths.TEST_SAMPLES_ROOT
        / game_id
        / "general_requirement.txt"
    ).resolve(strict=False)
    general_requirement = (
        general_requirement_path.read_text(encoding="utf-8")
        if general_requirement_path.is_file()
        else ""
    )
    if not ENGINE_CONTEXT_ROOT.is_dir():
        raise FileNotFoundError(
            "Engine Context directory was not found: "
            f"{ENGINE_CONTEXT_ROOT}"
        )
    if not any(
        path.is_file()
        for path in ENGINE_CONTEXT_ROOT.glob("*_api.md")
    ):
        raise FileNotFoundError(
            "Engine Context directory contains no API references: "
            f"{ENGINE_CONTEXT_ROOT}"
        )
    examples = _resolve_examples(task)

    system_prompt = read_required_text(
        SYSTEM_PROMPT_PATH,
        "Mechanic system Prompt",
    )
    task_template = read_required_text(
        TASK_PROMPT_PATH,
        "Mechanic task Prompt",
    )
    repair_template = read_required_text(
        REPAIR_PROMPT_PATH,
        "Mechanic repair Prompt",
    )
    read_required_text(
        SKILL_PATH,
        "Game Mechanic Generation Skill",
    )

    stage_dir = code_gen_stage_dir(
        workspace,
        mode=mode,
        repair_attempt=repair_attempt,
    )
    packet_path = stage_dir / "task_packet.json"
    agent_task = dict(task)
    for repeated_key in (
        "asset_sources",
        "motion_sources",
        "acceptance_criteria",
        "operator_execution",
        "mode",
        "repair",
    ):
        agent_task.pop(repeated_key, None)
    task_prompt = render_template(
        task_template,
        {
            "WORKSPACE": str(workspace),
            "PROJECT_NAME": project_name,
            "GAMEPLAY_MODULE_NAME": gameplay_module_name,
            "GAME_GENERATION_SKILL_PATH": str(SKILL_PATH),
            "TASK_PACKET_PATH": str(packet_path),
            "TASK_JSON": json_text(agent_task),
            "GENERAL_REQUIREMENT": general_requirement,
            "REQUIREMENT": requirement,
            "ACCEPTANCE_CRITERIA": json_text(
                task.get("acceptance_criteria", [])
            ),
            "ASSET_SOURCES": json_text(
                task.get("asset_sources", [])
            ),
            "MOTION_SOURCES": json_text(
                task.get("motion_sources", [])
            ),
            "ENGINE": engine,
            "ENGINE_CONTEXT_PATH": str(
                ENGINE_CONTEXT_ROOT
            ),
            "OPTIONAL_EXAMPLE_PATHS": json_text(
                [str(path) for path in examples]
            ),
        },
    )
    repair_prompt = ""
    if mode == "repair":
        repair_prompt = render_template(
            repair_template,
            {
                "WORKSPACE": str(workspace),
                "REPAIR_ATTEMPT": str(repair["attempt"]),
                "MAX_REPAIR_ATTEMPTS": str(
                    repair["max_attempts"]
                ),
                "FAILURES_JSON": json_text(
                    repair["failures"]
                ),
                "PREVIOUS_RESULT_JSON": json_text(
                    repair["previous_result"]
                ),
            },
        )

    read_only_paths = [
        SKILL_PATH,
        SYSTEM_PROMPT_PATH,
        TASK_PROMPT_PATH,
        REPAIR_PROMPT_PATH,
        ENGINE_CONTEXT_ROOT,
        requirement_path,
        *examples,
    ]
    if general_requirement_path.is_file():
        read_only_paths.append(general_requirement_path)
    _validate_boundaries(workspace, read_only_paths)

    packet_id = (
        f"{game_id}:{run_id}:{task_id}:"
        f"{mode}:{repair_attempt}"
    )
    packet = {
        "packet_id": packet_id,
        "generation_owner": "outer_agent",
        "game_id": game_id,
        "run_id": run_id,
        "task_kind": TASK_KIND,
        "task_id": task_id,
        "mode": mode,
        "repair_attempt": repair_attempt,
        "engine": engine,
        "project_name": project_name,
        "gameplay_module_name": gameplay_module_name,
        "task": agent_task,
        "context": {
            "general_requirement": general_requirement,
            "general_requirement_path": (
                str(general_requirement_path)
                if general_requirement_path.is_file()
                else ""
            ),
            "requirement": requirement,
            "requirement_path": str(requirement_path),
            "acceptance_criteria": _string_list(
                task.get("acceptance_criteria", []),
                "acceptance_criteria",
            ),
            "asset_sources": _mapping_list(
                task.get("asset_sources", []),
                "asset_sources",
            ),
            "motion_sources": _mapping_list(
                task.get("motion_sources", []),
                "motion_sources",
            ),
            "engine_context_path": str(
                ENGINE_CONTEXT_ROOT
            ),
            "skill_path": str(SKILL_PATH),
            "prompt_template_paths": {
                "system": str(SYSTEM_PROMPT_PATH),
                "task": str(TASK_PROMPT_PATH),
                "repair": str(REPAIR_PROMPT_PATH),
            },
            "example_paths": [
                str(path)
                for path in examples
            ],
        },
        "instructions": {
            "system_prompt": system_prompt,
            "task_prompt": task_prompt,
            "repair_prompt": repair_prompt,
        },
        "boundaries": {
            "allowed_write_root": str(workspace),
            "reserved_paths": list(
                DEFAULT_RESERVED_ROOTS
            ),
            "read_only_paths": [
                str(path)
                for path in read_only_paths
            ],
            "agent_may_execute_tests": False,
            "agent_may_declare_benchmark_success": False,
        },
        "repair": repair,
        "required_output_artifacts": _string_list(
            task.get("required_output_artifacts", []),
            "required_output_artifacts",
        ),
        "standard_output_layout": standard_layout,
    }
    instructions = (
        "# Prepared Mechanic Code Generation\n\n"
        f"Packet: `{packet_path}`\n\n"
        "Read the Skill and Engine API Reference paths from the packet "
        "before editing. Select the one API document that matches the "
        "task engine from the Engine Context directory.\n\n"
        "## System Guidance\n\n"
        f"{system_prompt.rstrip()}\n\n"
        "## Task Guidance\n\n"
        f"{task_prompt.rstrip()}\n"
    )
    if repair_prompt:
        instructions += (
            "\n## Repair Guidance\n\n"
            f"{repair_prompt.rstrip()}\n"
        )
    return prepare_workspace(
        packet,
        workspace=workspace,
        stage_dir=stage_dir,
        instructions=instructions,
        reserved_roots=DEFAULT_RESERVED_ROOTS,
        force=force,
    )


def finalize(
    packet_path: str | Path,
    *,
    summary: str = "",
) -> dict[str, Any]:
    """Finalize one directly edited Mechanic workspace."""
    return finalize_workspace(
        packet_path,
        summary=summary,
        artifact_checker=_required_artifact_checks,
    )


def _select_task(
    tasks_path: str | Path,
    *,
    game_id: str | None,
    task_id: str | None,
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
            "No matching Mechanic task was found"
        )
    if len(matches) > 1:
        raise ValueError(
            "Mechanic prepare handles one task at a time; "
            "pass --task-id"
        )
    return matches[0]


def _direct_task(args: argparse.Namespace) -> dict[str, Any]:
    if not args.engine:
        raise ValueError(
            "--engine is required with --requirement-path"
        )
    task: dict[str, Any] = {
        "game_id": args.game,
        "task_id": args.task_id or "demo",
        "engine": args.engine,
        "requirement_path": args.requirement_path,
        "project_name": args.project_name,
        "gameplay_module_name": args.module_name,
        "example_paths": list(args.example),
        "asset_sources": [],
        "motion_sources": [],
        "acceptance_criteria": [],
        "required_output_artifacts": [],
    }
    return {
        key: value
        for key, value in task.items()
        if value is not None and value != ""
    }


def _prepare_command(args: argparse.Namespace) -> int:
    run_id = (
        paths.new_run_id()
        if args.run_id == "auto"
        else args.run_id
    )
    if args.requirement_path:
        task = _direct_task(args)
    else:
        tasks_path = paths.resolve_tasks_path(
            TASK_KIND,
            args.tasks,
            args.game,
        )
        task = _select_task(
            tasks_path,
            game_id=args.game,
            task_id=args.task_id,
        )
    if args.mode:
        task["mode"] = args.mode
    if args.repair_json:
        task["mode"] = "repair"
        task["repair"] = read_json(
            args.repair_json,
            "Mechanic repair payload",
        )
    packet = prepare(
        task,
        run_id=run_id,
        output_dir=args.out_dir,
        default_game_id=args.game,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "packet_id": packet["packet_id"],
                "workspace": packet["workspace"],
                "task_packet_path": packet[
                    "artifacts"
                ]["task_packet_path"],
                "instructions_path": packet[
                    "artifacts"
                ]["instructions_path"],
                "skill_path": packet["context"][
                    "skill_path"
                ],
                "engine_context_path": packet[
                    "context"
                ]["engine_context_path"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _finalize_command(args: argparse.Namespace) -> int:
    result = finalize(
        args.packet,
        summary=args.summary,
    )
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or finalize one outer-Agent Mechanic "
            "code-generation task."
        )
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )
    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare one task packet and workspace.",
    )
    prepare_parser.add_argument("--game", default=None)
    prepare_parser.add_argument("--tasks", default=None)
    prepare_parser.add_argument("--task-id", default=None)
    prepare_parser.add_argument(
        "--run-id",
        default=paths.DEFAULT_RUN_ID,
    )
    prepare_parser.add_argument("--out-dir", default=None)
    prepare_parser.add_argument(
        "--mode",
        choices=["generate", "repair"],
        default=None,
    )
    prepare_parser.add_argument(
        "--repair-json",
        default=None,
    )
    prepare_parser.add_argument(
        "--requirement-path",
        default=None,
    )
    prepare_parser.add_argument("--engine", default=None)
    prepare_parser.add_argument(
        "--project-name",
        default=None,
    )
    prepare_parser.add_argument(
        "--module-name",
        default=None,
    )
    prepare_parser.add_argument(
        "--example",
        action="append",
        default=[],
    )
    prepare_parser.add_argument(
        "--force",
        action="store_true",
    )
    prepare_parser.set_defaults(handler=_prepare_command)

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Finalize a directly edited workspace.",
    )
    finalize_parser.add_argument(
        "--packet",
        required=True,
    )
    finalize_parser.add_argument(
        "--summary",
        default="",
    )
    finalize_parser.set_defaults(handler=_finalize_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (FileNotFoundError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
