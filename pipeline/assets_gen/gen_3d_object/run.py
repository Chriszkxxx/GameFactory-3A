"""
pipeline/assets_gen/gen_3d_object/run.py

3D object generation demo runner.

Loads Trellis2Model, injects it into Gen3DObjectOperator, reads tasks from
test_data/test_samples/3D_object_gen_collect.jsonl (or a single game's
object_tasks.jsonl), and writes GLB outputs grouped per game project:

    test_data/outputs/<game_id>/<run_id>/assets/3d_object/<task_id>/model.glb

Usage:
    # Run all tasks in the default jsonl
    python pipeline/assets_gen/gen_3d_object/run.py

    # Only one game project (prefers that game's own object_tasks.jsonl)
    python pipeline/assets_gen/gen_3d_object/run.py --game gameA_cyberpunk_shooter

    # Fresh timestamped run dir instead of overwriting <game>/default/
    python pipeline/assets_gen/gen_3d_object/run.py --run-id auto

    # Override model checkpoint path
    python pipeline/assets_gen/gen_3d_object/run.py \
        --ckpt /path/to/TRELLIS.2-4B

    # Run from a different jsonl
    python pipeline/assets_gen/gen_3d_object/run.py \
        --tasks test_data/test_samples/3D_object_gen_collect.jsonl

    # Legacy flat output (bypasses the per-game layout; debugging only)
    python pipeline/assets_gen/gen_3d_object/run.py --out-dir outputs/3d_object

    # Single demo (image only, no jsonl)
    python pipeline/assets_gen/gen_3d_object/run.py \
        --image path/to/image.png --task-id my_test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Make repo root importable regardless of CWD ───────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# ──────────────────────────────────────────────────────────────────────────────

from pipeline.common import paths  # noqa: E402

#: Registered task kind — keys into paths.TASK_* tables.
TASK_KIND = "3d_object"

# Local weight path (highest priority), falls back to HuggingFace download.
# Override via env var:  export TRELLIS2_CKPT=/your/local/path
DEFAULT_CKPT = "microsoft/TRELLIS-image-large"   # HF repo id — downloads weights on first run
DEFAULT_TASKS = paths.collect_jsonl(TASK_KIND)


def load_model(ckpt: str, device: str = "cuda", pipeline_type: str = "1024_cascade"):
    from models.gen_3d_object.trellis_2_model import Trellis2Model
    print(f"[run] Loading Trellis2Model from: {ckpt}")
    return Trellis2Model(model_path=ckpt, device=device, pipeline_type=pipeline_type)


def make_operator(
    model,
    output_dir: str | None = None,
    run_id: str = paths.DEFAULT_RUN_ID,
    default_game_id: str | None = None,
):
    """
    Build the operator.

    Leave `output_dir` unset for the per-game layout. Passing it keeps the legacy
    flat `<output_dir>/<task_id>.glb` behaviour.
    """
    from operators.gen_3d_object.operator import Gen3DObjectOperator
    return Gen3DObjectOperator(
        model=model,
        output_dir=output_dir,
        run_id=run_id,
        default_game_id=default_game_id,
    )


def generate(inp: dict, operator) -> dict:
    """Thin wrapper so eval.py can import and reuse."""
    return operator.run(inp)


def run_from_jsonl(tasks_path: str, operator, game_filter: str | None = None) -> list[dict]:
    """Iterate a jsonl file and run each task, optionally restricted to one game."""
    results = []
    for task, game_id in paths.iter_tasks(tasks_path, game_filter=game_filter):
        print(f"[run] game={game_id}  task_id={task.get('task_id', '?')}  "
              f"image={task.get('image_path', '?')}")
        result = generate(task, operator)
        print(f"       → glb={result['glb_path']}  ({result['elapsed_sec']}s)")
        results.append(result)
    return results


def main():
    import os

    parser = argparse.ArgumentParser(description="Run 3D object generation.")
    parser.add_argument("--ckpt",      default=os.environ.get("TRELLIS2_CKPT", DEFAULT_CKPT))
    parser.add_argument("--game",      default=None,
                        help=f"Game project id. Known: {paths.list_games() or '<none>'}")
    parser.add_argument("--tasks",     default=None,
                        help="Explicit jsonl path (overrides the --game task-list lookup)")
    parser.add_argument("--run-id",    default=paths.DEFAULT_RUN_ID,
                        help="Run directory name; 'auto' for a timestamp")
    parser.add_argument("--out-dir",   default=None,
                        help="Legacy flat output dir; bypasses the per-game layout")
    parser.add_argument("--device",    default="cuda")
    parser.add_argument("--pipeline-type", default="1024_cascade",
                        choices=["512", "1024", "1024_cascade", "1536_cascade"])
    # Single-demo mode
    parser.add_argument("--image",     default=None, help="Path to a single image (demo mode)")
    parser.add_argument("--task-id",   default="demo")
    parser.add_argument("--seed",      type=int, default=42)
    args = parser.parse_args()

    run_id = paths.new_run_id() if args.run_id == "auto" else args.run_id

    model = load_model(args.ckpt, device=args.device, pipeline_type=args.pipeline_type)
    operator = make_operator(model, output_dir=args.out_dir,
                             run_id=run_id, default_game_id=args.game)

    if args.image:
        # Single demo
        result = generate({"image_path": args.image, "task_id": args.task_id,
                           "seed": args.seed, "game_id": args.game}, operator)
        print(f"[run] Done: {result}")
        return

    # Batch from jsonl
    tasks_path = paths.resolve_tasks_path(TASK_KIND, args.tasks, args.game)
    print(f"[run] run_id={run_id}  tasks={paths.rel_to_repo(tasks_path)}")
    results = run_from_jsonl(str(tasks_path), operator, game_filter=args.game)
    if not results:
        print("[run] No matching tasks — nothing to do.")
        return

    if args.out_dir:
        # Legacy flat mode: keep the single summary next to the artifacts.
        summary_path = Path(args.out_dir) / "results_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[run] Wrote summary → {summary_path}")
    else:
        for p in paths.write_results_summary(results, TASK_KIND, run_id):
            print(f"[run] Wrote summary → {paths.rel_to_repo(p)}")


if __name__ == "__main__":
    main()
