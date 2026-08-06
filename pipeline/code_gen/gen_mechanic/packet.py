"""Prepare deterministic outer-Agent Mechanic task packets."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pipeline.code_gen.gen_mechanic.contracts import (
    MECHANIC_CONTRACT_FILENAME,
    MECHANIC_CONTRACT_SCHEMA,
)
from pipeline.common import paths
from pipeline.common.artifacts import (
    identifier,
    json_text,
    read_required_text,
    render_template,
    resolve_repo_path,
)
from pipeline.common.code_gen import (
    mapping_list,
    repair_payload,
    resolve_examples,
    string_list,
    validate_boundaries,
    validate_engine_context_root,
)
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
    repair, repair_attempt = repair_payload(task, mode)
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
    validate_engine_context_root(ENGINE_CONTEXT_ROOT)
    examples = resolve_examples(task)

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
    validate_boundaries(workspace, read_only_paths)

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
            "acceptance_criteria": string_list(
                task.get("acceptance_criteria", []),
                "acceptance_criteria",
            ),
            "asset_sources": mapping_list(
                task.get("asset_sources", []),
                "asset_sources",
            ),
            "motion_sources": mapping_list(
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
            "agent_may_generate_ui": False,
        },
        "mechanic_contract": {
            "path": str(
                workspace / MECHANIC_CONTRACT_FILENAME
            ),
            "schema_version": MECHANIC_CONTRACT_SCHEMA,
            "required_sections": [
                "state",
                "events",
                "commands",
            ],
            "gameplay_module": gameplay_module_name,
        },
        "repair": repair,
        "required_output_artifacts": string_list(
            task.get("required_output_artifacts", []),
            "required_output_artifacts",
        ),
        "standard_output_layout": standard_layout,
    }
    instructions = (
        "# Prepared Mechanic Code Generation\n\n"
        f"Packet: `{packet_path}`\n\n"
        "Read the Skill and Engine Context paths from the packet before "
        "editing. Select the one API document that matches the task "
        "engine from the Engine Context directory.\n\n"
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
