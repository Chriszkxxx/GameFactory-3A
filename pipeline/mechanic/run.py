"""Mechanic generation runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.common import paths  # noqa: E402


TASK_KIND = "mechanic"
DEFAULT_TASKS = paths.collect_jsonl(TASK_KIND)
DEFAULT_BACKEND = "stub"


def load_model(
    backend: str = DEFAULT_BACKEND,
    model_name: str = "",
    device: str = "cuda",
    *,
    timeout: float | None = None,
    max_turns: int | None = 8,
    sandbox_mode: str = "workspace-write",
):
    """Load one Duck-Typed Mechanic Agent backend."""
    backend_name = str(backend or "").strip().lower()
    print(
        "[run] Loading Mechanic Agent backend: "
        f"{backend_name or '<empty>'}"
    )
    if backend_name == "stub":
        from operators.gen_mechanic.agent import (
            StubAgent,
            make_stub_mechanic_files,
        )

        model = StubAgent(
            file_factory=make_stub_mechanic_files,
            timeout_sec=timeout,
            max_turns=max_turns,
        )
        model.model_name = model_name or "stub"
        model.device = device
        return model
    if backend_name == "codex":
        from operators.gen_mechanic.agent import CodexAgent

        model = CodexAgent(
            model_name=model_name,
            timeout_sec=timeout,
            max_turns=max_turns,
            sandbox_mode=sandbox_mode,
        )
        model.device = device
        return model
    if backend_name == "claude":
        raise NotImplementedError(
            f"{backend_name} backend is not implemented yet; "
            "use --backend stub or --backend codex"
        )
    raise ValueError(
        f"Unknown Mechanic Agent backend: {backend!r}"
    )


def make_operator(
    model,
    output_dir: str | None = None,
    run_id: str = paths.DEFAULT_RUN_ID,
    default_game_id: str | None = None,
):
    """Inject one loaded Agent backend into the Operator."""
    from operators.gen_mechanic.operator import (
        GenMechanicOperator,
    )

    return GenMechanicOperator(
        model=model,
        output_dir=output_dir,
        run_id=run_id,
        default_game_id=default_game_id,
    )


def generate(
    inp: dict,
    operator,
) -> dict:
    return operator.run(inp)


def run_from_jsonl(
    tasks_path: str,
    operator,
    game_filter: str | None = None,
) -> list[dict]:
    results = []
    for task, game_id in paths.iter_tasks(
        tasks_path,
        game_filter=game_filter,
    ):
        print(
            "[run] "
            f"game={game_id} "
            f"task_id={task.get('task_id', '?')} "
            f"engine={task.get('engine', '?')}"
        )
        result = generate(task, operator)
        print(
            "       -> "
            f"status={result['status']} "
            f"output={paths.rel_to_repo(result['output_dir'])} "
            f"({result['elapsed_sec']}s)"
        )
        results.append(result)
    return results


def _write_flat_summary(
    output_dir: str,
    results: list[dict],
) -> Path:
    path = Path(output_dir) / "results_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Run Mechanic code generation."
    )
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=["stub", "codex", "claude"],
    )
    parser.add_argument("--model", default="")
    parser.add_argument(
        "--game",
        default=None,
        help=(
            "Game project id. Known: "
            f"{paths.list_games() or '<none>'}"
        ),
    )
    parser.add_argument(
        "--tasks",
        default=None,
        help=(
            "Explicit jsonl path; overrides the "
            "--game task-list lookup"
        ),
    )
    parser.add_argument(
        "--run-id",
        default=paths.DEFAULT_RUN_ID,
        help=(
            "Run directory name; 'auto' for a timestamp"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=(
            "Legacy flat output dir; bypasses the "
            "per-game layout"
        ),
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--agent-timeout",
        type=float,
        default=None,
    )
    parser.add_argument(
        "--agent-max-turns",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--agent-sandbox",
        default="workspace-write",
        choices=[
            "read-only",
            "workspace-write",
            "danger-full-access",
        ],
        help=(
            "Sandbox mode used by the nested Codex CLI. "
            "Keep workspace-write unless an external sandbox "
            "already controls the generation process."
        ),
    )
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--engine", default="ue5")
    parser.add_argument(
        "--requirement-path",
        default=None,
    )
    parser.add_argument(
        "--engine-api-reference",
        default=None,
    )
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--module-name", default=None)
    parser.add_argument(
        "--example",
        action="append",
        default=[],
    )
    args = parser.parse_args(argv)

    if (
        args.requirement_path
        and not args.engine_api_reference
    ):
        parser.error(
            "--engine-api-reference is required "
            "with --requirement-path"
        )

    run_id = (
        paths.new_run_id()
        if args.run_id == "auto"
        else args.run_id
    )
    model = load_model(
        args.backend,
        args.model,
        args.device,
        timeout=args.agent_timeout,
        max_turns=args.agent_max_turns,
        sandbox_mode=args.agent_sandbox,
    )
    operator = make_operator(
        model,
        output_dir=args.out_dir,
        run_id=run_id,
        default_game_id=args.game,
    )

    if args.requirement_path:
        task = {
            "game_id": args.game,
            "task_id": args.task_id or "demo",
            "engine": args.engine,
            "requirement_path": (
                args.requirement_path
            ),
            "engine_api_reference_path": (
                args.engine_api_reference
            ),
            "project_name": args.project_name,
            "gameplay_module_name": (
                args.module_name
            ),
            "example_paths": list(args.example),
            "asset_sources": [],
            "motion_sources": [],
            "acceptance_criteria": [],
            "required_output_artifacts": [
                "project_file",
                "plugin_dir",
                "launch_script",
                "demo_outputs_dir",
            ],
        }
        task = {
            key: value
            for key, value in task.items()
            if value is not None and value != ""
        }
        result = generate(task, operator)
        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return 0 if result["ok"] else 1

    tasks_path = paths.resolve_tasks_path(
        TASK_KIND,
        args.tasks,
        args.game,
    )
    print(
        f"[run] run_id={run_id} "
        f"tasks={paths.rel_to_repo(tasks_path)} "
        f"backend={args.backend}"
    )
    results = run_from_jsonl(
        str(tasks_path),
        operator,
        game_filter=args.game,
    )
    if not results:
        print("[run] No matching tasks - nothing to do.")
        return 0

    if args.out_dir:
        summary = _write_flat_summary(
            args.out_dir,
            results,
        )
        print(f"[run] Wrote summary -> {summary}")
    else:
        for summary in paths.write_results_summary(
            results,
            TASK_KIND,
            run_id,
        ):
            print(
                "[run] Wrote summary -> "
                f"{paths.rel_to_repo(summary)}"
            )
    return 0 if all(
        result.get("ok")
        for result in results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
