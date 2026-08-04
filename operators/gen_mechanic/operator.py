"""
Mechanic generation Operator.

The Operator assembles one engine-neutral Agent request, invokes the injected
Duck-Typed `model.run(request)` backend, validates its file report, and
preserves the complete Mechanic artifact on success or failure.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .agent import (
    validate_agent_request,
    validate_agent_result,
)


TASK_KIND = "mechanic"
REPO_ROOT = Path(__file__).resolve().parents[2]
MECHANIC_ROOT = Path(__file__).resolve().parent
SKILL_PATH = (
    MECHANIC_ROOT
    / "skills"
    / "game_generation.md"
)
PROMPTS_ROOT = MECHANIC_ROOT / "prompts"
OPERATOR_OWNED_PATHS = (
    "meta.json",
    "demo_outputs",
    "evaluation",
)


def _read_text(path: Path, name: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(
            f"{name} was not found: {path}"
        )
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"{name} is empty: {path}")
    return text


def _repo_path(value: str | Path, name: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve(strict=False)


def _identifier(value: Any, prefix: str) -> str:
    parts = re.findall(
        r"[A-Za-z0-9]+",
        str(value or ""),
    )
    candidate = "".join(
        part[:1].upper() + part[1:]
        for part in parts
    )
    if not candidate:
        candidate = prefix
    if candidate[0].isdigit():
        candidate = prefix + candidate
    return candidate


def _render_template(
    template: str,
    values: Mapping[str, str],
) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(
            f"{{{{{key}}}}}",
            value,
        )
    unresolved = sorted(
        set(
            re.findall(
                r"\{\{[A-Z0-9_]+\}\}",
                rendered,
            )
        )
    )
    if unresolved:
        raise ValueError(
            "Prompt template has unresolved markers: "
            + ", ".join(unresolved)
        )
    return rendered


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _json_text(value) + "\n",
        encoding="utf-8",
    )


def _write_transcript(
    path: Path,
    transcript: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(
                entry,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
            for entry in transcript
        ),
        encoding="utf-8",
    )


def _reported_operator_owned_paths(
    result: Mapping[str, Any],
) -> list[str]:
    invalid: list[str] = []
    for field in (
        "generated_files",
        "modified_files",
        "deleted_files",
    ):
        for relative_path in result.get(field, []):
            parts = PurePosixPath(relative_path).parts
            if not parts:
                continue
            if (
                parts[0] == OPERATOR_OWNED_PATHS[0]
                or parts[0] == OPERATOR_OWNED_PATHS[1]
            ):
                invalid.append(relative_path)
    return invalid


class GenMechanicOperator:
    """Generate one preserved Mechanic artifact through an injected Agent."""

    def __init__(
        self,
        model: Any,
        output_dir: str | None = None,
        run_id: str = "default",
        default_game_id: str | None = None,
    ) -> None:
        self.model = model
        self.run_id = run_id
        self.default_game_id = default_game_id
        self.output_dir = (
            Path(output_dir).expanduser().resolve(
                strict=False
            )
            if output_dir
            else None
        )
        if self.output_dir is not None:
            self.output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

    def _task_dir(
        self,
        inp: dict[str, Any],
        task_id: str,
    ) -> tuple[str, Path]:
        if self.output_dir is not None:
            game_id = str(
                inp.get("game_id")
                or inp.get("game")
                or self.default_game_id
                or ""
            )
            task_dir = self.output_dir / task_id
            task_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
            return game_id, task_dir
        from pipeline.common import paths

        game_id = paths.infer_game_id(
            inp,
            fallback=self.default_game_id,
        )
        task_dir = paths.task_output_dir(
            game_id,
            TASK_KIND,
            task_id,
            run_id=self.run_id,
        )
        return game_id, task_dir

    def _engine_api_path(
        self,
        inp: Mapping[str, Any],
    ) -> Path:
        value = inp.get(
            "engine_api_reference_path"
        )
        return _repo_path(
            str(value or ""),
            "engine_api_reference_path",
        )

    def _example_paths(
        self,
        inp: Mapping[str, Any],
    ) -> list[Path]:
        raw_examples = (
            inp.get("example_paths")
            or inp.get("examples")
            or []
        )
        if isinstance(
            raw_examples,
            (str, Path, Mapping),
        ):
            raw_examples = [raw_examples]
        result: list[Path] = []
        for item in raw_examples:
            value = (
                item.get("path")
                if isinstance(item, Mapping)
                else item
            )
            path = _repo_path(
                str(value or ""),
                "example path",
            )
            if not path.exists():
                raise FileNotFoundError(
                    f"Example path was not found: {path}"
                )
            result.append(path)
        return result

    def _build_request(
        self,
        inp: dict[str, Any],
        *,
        game_id: str,
        task_id: str,
        task_dir: Path,
        project_name: str,
        gameplay_module_name: str,
    ) -> dict[str, Any]:
        mode = str(
            inp.get("mode") or "generate"
        ).strip().lower()
        if mode not in {"generate", "repair"}:
            raise ValueError(
                "Mechanic task mode must be generate or repair"
            )
        engine = str(
            inp.get("engine") or ""
        ).strip()
        if not engine:
            raise ValueError(
                "Mechanic task must contain engine"
            )
        requirement_path = _repo_path(
            str(inp.get("requirement_path") or ""),
            "requirement_path",
        )
        requirement = _read_text(
            requirement_path,
            "Mechanic requirement",
        )
        general_requirement_path = (
            REPO_ROOT
            / "test_data"
            / "test_samples"
            / game_id
            / "general_requirement.txt"
        )
        general_requirement = (
            general_requirement_path.read_text(
                encoding="utf-8"
            )
            if general_requirement_path.is_file()
            else ""
        )
        api_path = self._engine_api_path(inp)
        examples = self._example_paths(inp)
        system_prompt = _read_text(
            PROMPTS_ROOT / "system.md",
            "Mechanic system prompt",
        )
        task_template = _read_text(
            PROMPTS_ROOT / "task.md",
            "Mechanic task prompt",
        )
        repair_template = _read_text(
            PROMPTS_ROOT / "repair.md",
            "Mechanic repair prompt",
        )
        _read_text(
            SKILL_PATH,
            "Game Mechanic Generation Skill",
        )
        agent_task = dict(inp)
        for repeated_key in (
            "asset_sources",
            "motion_sources",
            "acceptance_criteria",
            "operator_execution",
            "mode",
            "repair",
        ):
            agent_task.pop(repeated_key, None)
        task_prompt = _render_template(
            task_template,
            {
                "WORKSPACE": str(task_dir),
                "PROJECT_NAME": project_name,
                "GAMEPLAY_MODULE_NAME": (
                    gameplay_module_name
                ),
                "GAME_GENERATION_SKILL_PATH": str(
                    SKILL_PATH
                ),
                "TASK_JSON": _json_text(agent_task),
                "GENERAL_REQUIREMENT": (
                    general_requirement
                ),
                "REQUIREMENT": requirement,
                "ACCEPTANCE_CRITERIA": _json_text(
                    inp.get(
                        "acceptance_criteria",
                        [],
                    )
                ),
                "ASSET_SOURCES": _json_text(
                    inp.get("asset_sources", [])
                ),
                "MOTION_SOURCES": _json_text(
                    inp.get("motion_sources", [])
                ),
                "ENGINE_API_REFERENCE_PATH": str(
                    api_path
                ),
                "OPTIONAL_EXAMPLE_PATHS": _json_text(
                    [str(path) for path in examples]
                ),
            },
        )
        repair: dict[str, Any] = {}
        repair_prompt = ""
        request_attempt = 0
        if mode == "repair":
            raw_repair = inp.get("repair")
            if not isinstance(raw_repair, Mapping):
                raise TypeError(
                    "repair must be an object in repair mode"
                )
            repair = dict(raw_repair)
            request_attempt = int(
                repair.get("attempt") or 0
            )
            repair_prompt = _render_template(
                repair_template,
                {
                    "WORKSPACE": str(task_dir),
                    "REPAIR_ATTEMPT": str(
                        repair.get("attempt") or ""
                    ),
                    "MAX_REPAIR_ATTEMPTS": str(
                        repair.get("max_attempts") or ""
                    ),
                    "FAILURES_JSON": _json_text(
                        repair.get("failures", [])
                    ),
                    "PREVIOUS_AGENT_RESULT_JSON": (
                        _json_text(
                            repair.get(
                                "previous_result",
                                {},
                            )
                        )
                    ),
                },
            )
        read_only_paths = [
            api_path,
            SKILL_PATH,
            requirement_path,
            *examples,
        ]
        if general_requirement_path.is_file():
            read_only_paths.append(
                general_requirement_path
            )
        request = {
            "request_id": (
                f"{game_id}:{task_id}:"
                f"{mode}:{request_attempt}"
            ),
            "mode": mode,
            "workspace": str(task_dir),
            "system_prompt": system_prompt,
            "task_prompt": task_prompt,
            "repair_prompt": repair_prompt,
            "context": {
                "task": agent_task,
                "project_name": project_name,
                "gameplay_module_name": (
                    gameplay_module_name
                ),
                "general_requirement": (
                    general_requirement
                ),
                "requirement": requirement,
                "acceptance_criteria": inp.get(
                    "acceptance_criteria",
                    [],
                ),
                "asset_sources": inp.get(
                    "asset_sources",
                    [],
                ),
                "motion_sources": inp.get(
                    "motion_sources",
                    [],
                ),
                "engine": engine,
                "engine_api_reference": {
                    "path": str(api_path),
                    "read_only": True,
                },
                "skill": {
                    "path": str(SKILL_PATH),
                    "read_only": True,
                },
                "examples": [
                    {
                        "path": str(path),
                        "read_only": True,
                    }
                    for path in examples
                ],
            },
            "constraints": {
                "allowed_write_roots": [
                    str(task_dir),
                ],
                "read_only_paths": [
                    str(path)
                    for path in read_only_paths
                ],
                "agent_may_execute_tests": False,
                (
                    "agent_may_declare_benchmark_success"
                ): False,
                "agent_may_modify": [
                    "game_owned_source",
                    "game_owned_tests",
                ],
                "agent_must_not_modify": [
                    "framework",
                    "evaluation",
                    "operator_metadata",
                ],
            },
            "limits": {
                "timeout_sec": getattr(
                    self.model,
                    "timeout_sec",
                    None,
                ),
                "max_turns": getattr(
                    self.model,
                    "max_turns",
                    None,
                ),
            },
            "repair": repair,
            "metadata": {
                "game_id": game_id,
                "run_id": self.run_id,
                "task_kind": TASK_KIND,
                "task_id": task_id,
                "mode": mode,
            },
        }
        return validate_agent_request(request)

    def run(self, inp: dict) -> dict:
        started = time.time()
        mode = str(
            inp.get("mode") or "generate"
        ).strip().lower()
        repair_payload = inp.get("repair")
        repair_attempt = (
            int(repair_payload.get("attempt") or 0)
            if isinstance(repair_payload, Mapping)
            else 0
        )
        task_id = str(
            inp.get("task_id")
            or f"task_{int(started)}"
        )
        game_id, task_dir = self._task_dir(
            inp,
            task_id,
        )
        demo_outputs = task_dir / "demo_outputs"
        demo_outputs.mkdir(
            parents=True,
            exist_ok=True,
        )
        agent_outputs = (
            demo_outputs
            if mode == "generate"
            else (
                demo_outputs
                / "repairs"
                / f"attempt_{repair_attempt:02d}"
            )
        )
        agent_outputs.mkdir(
            parents=True,
            exist_ok=True,
        )
        project_name = _identifier(
            inp.get("project_name")
            or f"AAAGame_{task_id}",
            "AAAGame",
        )
        gameplay_module_name = _identifier(
            inp.get("gameplay_module_name")
            or f"{project_name}_Gameplay",
            "GeneratedGameplay",
        )
        engine = str(
            inp.get("engine") or ""
        ).strip()
        errors: list[str] = []
        warnings: list[str] = []
        request: dict[str, Any] | None = None
        agent_result: dict[str, Any] | None = None

        try:
            request = self._build_request(
                inp,
                game_id=game_id,
                task_id=task_id,
                task_dir=task_dir,
                project_name=project_name,
                gameplay_module_name=(
                    gameplay_module_name
                ),
            )
            _write_json(
                agent_outputs / "agent_request.json",
                request,
            )
            raw_result = self.model.run(request)
            agent_result = validate_agent_result(
                raw_result,
                request_id=request["request_id"],
                workspace=task_dir,
            )
            invalid_paths = (
                _reported_operator_owned_paths(
                    agent_result
                )
            )
            if invalid_paths:
                raise ValueError(
                    "Agent reported Operator-owned paths: "
                    + ", ".join(invalid_paths)
                )
            warnings.extend(
                agent_result["warnings"]
            )
            errors.extend(agent_result["errors"])
        except Exception as exc:
            errors.append(
                f"{type(exc).__name__}: {exc}"
            )
            if agent_result is None:
                agent_result = {
                    "ok": False,
                    "request_id": (
                        request["request_id"]
                        if request is not None
                        else (
                            f"{game_id}:{task_id}:"
                            f"{mode}:{repair_attempt}"
                        )
                    ),
                    "status": "failed",
                    "generated_files": [],
                    "modified_files": [],
                    "deleted_files": [],
                    "diagnostics": [],
                    "warnings": [],
                    "errors": list(errors),
                    "transcript": [],
                    "usage": {},
                    "payload": {
                        "backend": type(
                            self.model
                        ).__name__,
                    },
                }

        if agent_result is None:
            raise RuntimeError(
                "Mechanic Agent result was not created"
        )
        _write_json(
            agent_outputs / "agent_result.json",
            agent_result,
        )
        _write_transcript(
            agent_outputs / "agent_transcript.jsonl",
            agent_result.get("transcript", []),
        )

        reported_changes = [
            *agent_result.get("generated_files", []),
            *agent_result.get("modified_files", []),
            *agent_result.get("deleted_files", []),
        ]
        if agent_result.get("ok") and not reported_changes:
            errors.append(
                "Mechanic Agent completed without reporting "
                "workspace file changes"
            )

        ok = bool(
            agent_result.get("ok")
            and not errors
        )
        elapsed = round(
            time.time() - started,
            2,
        )
        result = {
            "ok": ok,
            "status": (
                "completed"
                if ok
                else "failed"
            ),
            "task_id": task_id,
            "game_id": game_id,
            "run_id": self.run_id,
            "task_kind": TASK_KIND,
            "mode": mode,
            "engine": engine,
            "project_name": project_name,
            "gameplay_module_name": (
                gameplay_module_name
            ),
            "output_dir": str(task_dir),
            "workspace": str(task_dir),
            "agent_request_path": str(
                agent_outputs / "agent_request.json"
            ) if request is not None else "",
            "agent_result_path": str(
                agent_outputs / "agent_result.json"
            ),
            "agent_transcript_path": str(
                agent_outputs
                / "agent_transcript.jsonl"
            ),
            "generated_files": list(
                agent_result.get(
                    "generated_files",
                    [],
                )
            ),
            "modified_files": list(
                agent_result.get(
                    "modified_files",
                    [],
                )
            ),
            "deleted_files": list(
                agent_result.get(
                    "deleted_files",
                    [],
                )
            ),
            "warnings": list(dict.fromkeys(warnings)),
            "errors": list(dict.fromkeys(errors)),
            "elapsed_sec": elapsed,
            "model": type(self.model).__name__,
        }
        from pipeline.common import paths

        paths.write_task_meta(
            task_dir,
            result,
        )
        return result

    def run_batch(
        self,
        inputs: list[dict],
    ) -> list[dict]:
        return [
            self.run(inp)
            for inp in inputs
        ]
