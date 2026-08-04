"""Run BVH/FBX -> Puppeteer ``GLB + rig.txt`` motion retargeting."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.common import paths  # noqa: E402


TASK_KIND = "retarget"
DEFAULT_CKPT = sys.executable
DEFAULT_TASKS = paths.collect_jsonl(TASK_KIND)


def load_model(ckpt: str, device: str = "cpu", verbose: bool = False):
    """Load the file-oriented bpy retarget wrapper."""
    from models.retarget.puppeteer_retarget_model import PuppeteerRetargetModel

    print(f"[run] Loading PuppeteerRetargetModel with bpy Python: {ckpt}")
    return PuppeteerRetargetModel(
        model_path=ckpt,
        device=device,
        verbose=verbose,
    )


def make_operator(
    model,
    output_dir: str | None = None,
    run_id: str = paths.DEFAULT_RUN_ID,
    default_game_id: str | None = None,
):
    """Inject one loaded retarget model into the task operator."""
    from operators.retarget.operator import RetargetOperator

    return RetargetOperator(
        model=model,
        output_dir=output_dir,
        run_id=run_id,
        default_game_id=default_game_id,
    )


def generate(inp: dict, operator) -> dict:
    """Run one task through the already-constructed operator."""
    return operator.run(inp)


def run_from_jsonl(
    tasks_path: str,
    operator,
    game_filter: str | None = None,
) -> list[dict]:
    """Run tasks from the standard AAAGameForge JSONL iterator."""
    results = []
    for task, game_id in paths.iter_tasks(
        tasks_path,
        game_filter=game_filter,
    ):
        print(
            f"[run] game={game_id}  task_id={task.get('task_id', '?')}  "
            f"motion={task.get('source_motion_path', '?')}"
        )
        result = generate(task, operator)
        print(
            f"       -> fbx={result['retargeted_fbx_path']}  "
            f"({result['elapsed_sec']}s)"
        )
        results.append(result)
    return results


def main() -> None:
    import os

    parser = argparse.ArgumentParser(
        description=(
            "Retarget a BVH/FBX animation onto a Puppeteer GLB + rig.txt target."
        )
    )
    parser.add_argument(
        "--ckpt",
        "--bpy-python",
        dest="bpy_python",
        default=os.environ.get("AAAGF_RETARGET_BPY_PYTHON", DEFAULT_CKPT),
        help="Python 3.11 executable that can import bpy, numpy and trimesh.",
    )
    parser.add_argument(
        "--game",
        default=None,
        help=f"Game project id. Known: {paths.list_games() or '<none>'}",
    )
    parser.add_argument(
        "--tasks",
        default=None,
        help="Explicit JSONL path; overrides the --game task-list lookup.",
    )
    parser.add_argument("--run-id", default=paths.DEFAULT_RUN_ID)
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Legacy flat output directory.",
    )
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--verbose", action="store_true")

    # Single-task demo mode.
    parser.add_argument("--source-motion", default=None)
    parser.add_argument("--target-glb", default=None)
    parser.add_argument("--target-rig", default=None)
    parser.add_argument("--mapping", default=None)
    parser.add_argument("--task-id", default="demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--global-scale", type=float, default=1.0)
    parser.add_argument("--root-scale", type=float, default=None)
    parser.add_argument("--max-delta-deg", type=float, default=0.0)
    parser.add_argument("--bake-root-to-bone", action="store_true")
    parser.add_argument(
        "--no-anim-only",
        action="store_true",
        help="Do not export the armature-only FBX.",
    )
    args = parser.parse_args()

    run_id = paths.new_run_id() if args.run_id == "auto" else args.run_id
    model = load_model(
        args.bpy_python,
        device=args.device,
        verbose=args.verbose,
    )
    operator = make_operator(
        model,
        output_dir=args.out_dir,
        run_id=run_id,
        default_game_id=args.game,
    )

    if args.source_motion:
        missing = [
            flag
            for flag, value in (
                ("--target-glb", args.target_glb),
                ("--target-rig", args.target_rig),
            )
            if not value
        ]
        if missing:
            parser.error(
                "--source-motion demo mode also requires "
                + " and ".join(missing)
            )
        result = generate(
            {
                "game_id": args.game,
                "task_id": args.task_id,
                "source_motion_path": args.source_motion,
                "target_glb_path": args.target_glb,
                "target_rig_path": args.target_rig,
                "mapping_path": args.mapping,
                "seed": args.seed,
                "fps": args.fps,
                "global_scale": args.global_scale,
                "root_scale": args.root_scale,
                "max_delta_deg": args.max_delta_deg,
                "bake_root_to_bone": args.bake_root_to_bone,
                "export_anim_only": not args.no_anim_only,
            },
            operator,
        )
        print(f"[run] Done: {result}")
        return

    tasks_path = paths.resolve_tasks_path(TASK_KIND, args.tasks, args.game)
    print(f"[run] run_id={run_id}  tasks={paths.rel_to_repo(tasks_path)}")
    results = run_from_jsonl(
        str(tasks_path),
        operator,
        game_filter=args.game,
    )
    if not results:
        print("[run] No matching tasks - nothing to do.")
        return

    if args.out_dir:
        summary_path = Path(args.out_dir) / "results_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(results, indent=2),
            encoding="utf-8",
        )
        print(f"[run] Wrote summary -> {summary_path}")
    else:
        for summary_path in paths.write_results_summary(
            results,
            TASK_KIND,
            run_id,
        ):
            print(
                "[run] Wrote summary -> "
                f"{paths.rel_to_repo(summary_path)}"
            )


if __name__ == "__main__":
    main()
