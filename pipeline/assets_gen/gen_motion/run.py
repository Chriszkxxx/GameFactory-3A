"""Run unified rigging, text-to-motion and retarget tasks."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.common import paths  # noqa: E402


TASK_KIND = "motion"
DEFAULT_TASKS = paths.collect_jsonl(TASK_KIND)


def load_retarget_runtime(
    bpy_python: str,
    device: str = "cpu",
) -> str:
    """Validate and return the Python executable used by the bpy function."""
    from operators.gen_motion.funcs.retarget_motion import (
        ensure_retarget_runtime,
    )

    print(f"[run] Validating retarget bpy Python: {bpy_python}")
    return ensure_retarget_runtime(bpy_python, device=device)


def load_puppeteer_model(
    model_path: str,
    *,
    python_bin: str | None = None,
    device: str = "cuda",
    gpu: int = 0,
    skeleton_ckpt: str | None = None,
    skinning_ckpt: str | None = None,
    verbose: bool = False,
):
    """Construct and validate the Puppeteer wrapper lazily."""
    from models.gen_motion.puppeteer_model import (
        DEFAULT_SKELETON_CKPT,
        DEFAULT_SKINNING_CKPT,
        PuppeteerModel,
    )

    print(f"[run] Loading Puppeteer runtime from: {model_path}")
    model = PuppeteerModel(
        model_path,
        device=device,
        python_bin=python_bin,
        skeleton_ckpt=skeleton_ckpt or DEFAULT_SKELETON_CKPT,
        skinning_ckpt=skinning_ckpt or DEFAULT_SKINNING_CKPT,
        gpu=gpu,
        verbose=verbose,
    )
    model.load()
    return model


def load_momask_model(
    model_path: str,
    *,
    python_bin: str | None = None,
    device: str = "cuda",
    gpu: int = 0,
    name: str | None = None,
    res_name: str | None = None,
    vq_name: str | None = None,
    verbose: bool = False,
):
    """Construct and validate the MoMask wrapper lazily."""
    from models.gen_motion.momask_model import (
        DEFAULT_RES_NAME,
        DEFAULT_T2M_NAME,
        DEFAULT_VQ_NAME,
        MoMaskModel,
    )

    print(f"[run] Loading MoMask runtime from: {model_path}")
    model = MoMaskModel(
        model_path,
        device=device,
        python_bin=python_bin,
        gpu=gpu,
        name=name or DEFAULT_T2M_NAME,
        res_name=res_name or DEFAULT_RES_NAME,
        vq_name=vq_name or DEFAULT_VQ_NAME,
        verbose=verbose,
    )
    model.load()
    return model


def make_operator(
    bpy_python: str | None = None,
    output_dir: str | None = None,
    run_id: str = paths.DEFAULT_RUN_ID,
    default_game_id: str | None = None,
    *,
    puppeteer_model: Any | None = None,
    momask_model: Any | None = None,
    device: str = "cpu",
    verbose: bool = False,
):
    """Inject only the runtimes required by the requested motion tasks."""
    from operators.gen_motion.operator import GenMotionOperator

    return GenMotionOperator(
        bpy_python=bpy_python,
        puppeteer_model=puppeteer_model,
        momask_model=momask_model,
        output_dir=output_dir,
        run_id=run_id,
        default_game_id=default_game_id,
        device=device,
        verbose=verbose,
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
        task_type = task.get("task_type", "retarget")
        print(
            f"[run] game={game_id}  task_id={task.get('task_id', '?')}  "
            f"task_type={task_type}"
        )
        result = generate(task, operator)
        primary = (
            result.get("retargeted_fbx_path")
            or result.get("motion_bvh_path")
            or result.get("rig_path")
        )
        print(f"       -> artifact={primary}  ({result['elapsed_sec']}s)")
        results.append(result)
    return results


def _required_task_types(
    tasks_path: str,
    game_filter: str | None,
) -> set[str]:
    return {
        str(task.get("task_type", "retarget")).lower()
        for task, _ in paths.iter_tasks(tasks_path, game_filter=game_filter)
    }


def _build_operator_for_types(
    args: argparse.Namespace,
    task_types: set[str],
    run_id: str,
):
    needs_rig = bool(task_types & {"rig", "humanoid"})
    needs_motion = bool(task_types & {"text_to_motion", "humanoid"})
    needs_retarget = bool(task_types & {"retarget", "humanoid"})

    puppeteer = None
    if needs_rig:
        if not args.puppeteer_model_path:
            raise RuntimeError(
                "This task needs Puppeteer. Pass --puppeteer-model-path or "
                "set AAAGF_PUPPETEER_MODEL_PATH."
            )
        puppeteer = load_puppeteer_model(
            args.puppeteer_model_path,
            python_bin=args.puppeteer_python,
            device=args.model_device,
            gpu=args.gpu,
            skeleton_ckpt=args.skeleton_ckpt,
            skinning_ckpt=args.skinning_ckpt,
            verbose=args.verbose,
        )

    momask = None
    if needs_motion:
        if not args.momask_model_path:
            raise RuntimeError(
                "This task needs MoMask. Pass --momask-model-path or set "
                "AAAGF_MOMASK_MODEL_PATH."
            )
        momask = load_momask_model(
            args.momask_model_path,
            python_bin=args.momask_python,
            device=args.model_device,
            gpu=args.gpu,
            name=args.momask_name,
            res_name=args.momask_res_name,
            vq_name=args.momask_vq_name,
            verbose=args.verbose,
        )

    bpy_python = None
    if needs_retarget:
        if not args.bpy_python:
            raise RuntimeError(
                "This task needs bpy. Pass --bpy-python or set "
                "AAAGF_RETARGET_BPY_PYTHON."
            )
        bpy_python = load_retarget_runtime(
            args.bpy_python,
            device=args.retarget_device,
        )

    return make_operator(
        bpy_python,
        puppeteer_model=puppeteer,
        momask_model=momask,
        output_dir=args.out_dir,
        run_id=run_id,
        default_game_id=args.game,
        device=args.retarget_device,
        verbose=args.verbose,
    )


def _demo_task(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict:
    task_type = args.task_type
    required: list[tuple[str, Any]] = []
    if task_type == "retarget":
        required.extend(
            [
                ("--source-motion", args.source_motion),
                ("--target-glb", args.target_glb),
                ("--target-rig", args.target_rig),
            ]
        )
    elif task_type == "rig":
        required.append(("--target-glb", args.target_glb))
    elif task_type == "text_to_motion":
        required.append(("--prompt", args.prompt))
    elif task_type == "humanoid":
        required.extend(
            [
                ("--target-glb", args.target_glb),
                ("--prompt", args.prompt),
            ]
        )
    missing = [flag for flag, value in required if not value]
    if missing:
        parser.error(
            f"--task-type {task_type} requires " + ", ".join(missing)
        )
    return {
        "game_id": args.game,
        "task_id": args.task_id,
        "task_type": task_type,
        "source_motion_path": args.source_motion,
        "target_glb_path": args.target_glb,
        "target_rig_path": args.target_rig,
        "mapping_path": args.mapping,
        "prompt": args.prompt,
        "seed": args.seed,
        "fps": args.fps,
        "motion_length": args.motion_length,
        "use_ik": not args.no_ik,
        "in_place": args.in_place,
        "global_scale": args.global_scale,
        "root_scale": args.root_scale,
        "max_delta_deg": args.max_delta_deg,
        "bake_root_to_bone": args.bake_root_to_bone,
        "export_anim_only": not args.no_anim_only,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run gen_motion tasks: Puppeteer rigging, MoMask text-to-motion, "
            "world-delta retargeting, or the complete humanoid chain."
        )
    )
    parser.add_argument(
        "--task-type",
        default="retarget",
        choices=["retarget", "rig", "text_to_motion", "humanoid"],
    )
    parser.add_argument(
        "--bpy-python",
        default=os.environ.get("AAAGF_RETARGET_BPY_PYTHON"),
        help="Python 3.11 executable that can import bpy, numpy and trimesh.",
    )
    parser.add_argument(
        "--puppeteer-model-path",
        default=os.environ.get("AAAGF_PUPPETEER_MODEL_PATH"),
    )
    parser.add_argument(
        "--puppeteer-python",
        default=os.environ.get("AAAGF_PUPPETEER_PYTHON"),
    )
    parser.add_argument("--skeleton-ckpt", default=None)
    parser.add_argument("--skinning-ckpt", default=None)
    parser.add_argument(
        "--momask-model-path",
        default=os.environ.get("AAAGF_MOMASK_MODEL_PATH"),
    )
    parser.add_argument(
        "--momask-python",
        default=os.environ.get("AAAGF_MOMASK_PYTHON"),
    )
    parser.add_argument("--momask-name", default=None)
    parser.add_argument("--momask-res-name", default=None)
    parser.add_argument("--momask-vq-name", default=None)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument(
        "--model-device",
        default="cuda",
        choices=["cpu", "cuda"],
    )
    parser.add_argument(
        "--retarget-device",
        "--device",
        dest="retarget_device",
        default="cpu",
        choices=["cpu", "cuda"],
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
    parser.add_argument("--verbose", action="store_true")

    parser.add_argument("--source-motion", default=None)
    parser.add_argument("--target-glb", default=None)
    parser.add_argument("--target-rig", default=None)
    parser.add_argument("--mapping", default=None)
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--task-id", default="demo")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--motion-length", type=int, default=0)
    parser.add_argument("--no-ik", action="store_true")
    parser.add_argument("--in-place", action="store_true")
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
    demo_requested = any(
        (
            args.source_motion,
            args.target_glb,
            args.target_rig,
            args.prompt,
        )
    )
    if demo_requested:
        task = _demo_task(args, parser)
        operator = _build_operator_for_types(
            args,
            {args.task_type},
            run_id,
        )
        print(f"[run] Done: {generate(task, operator)}")
        return

    tasks_path = paths.resolve_tasks_path(TASK_KIND, args.tasks, args.game)
    task_types = _required_task_types(str(tasks_path), args.game)
    if not task_types:
        print("[run] No matching tasks - nothing to do.")
        return
    operator = _build_operator_for_types(args, task_types, run_id)
    print(f"[run] run_id={run_id}  tasks={paths.rel_to_repo(tasks_path)}")
    results = run_from_jsonl(
        str(tasks_path),
        operator,
        game_filter=args.game,
    )

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
