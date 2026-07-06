"""
pipeline/assets_gen/gen_3d_object/run.py

3D object generation demo runner.

Loads Trellis2Model, injects it into Gen3DObjectOperator, reads tasks from
test_data/test_samples/3D_object_gen_collect.jsonl, and writes GLB outputs.

Usage:
    # Run all tasks in the default jsonl
    python pipeline/assets_gen/gen_3d_object/run.py

    # Override model checkpoint path
    python pipeline/assets_gen/gen_3d_object/run.py \
        --ckpt /path/to/TRELLIS.2-4B

    # Run from a different jsonl
    python pipeline/assets_gen/gen_3d_object/run.py \
        --tasks test_data/test_samples/3D_object_gen_collect.jsonl \
        --out-dir outputs/3d_object

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

# Local weight path (highest priority), falls back to HuggingFace download.
# Override via env var:  export TRELLIS2_CKPT=/your/local/path
DEFAULT_CKPT = "microsoft/TRELLIS-image-large"   # HF repo id — downloads weights on first run
DEFAULT_TASKS = _REPO_ROOT / "test_data" / "test_samples" / "3D_object_gen_collect.jsonl"
DEFAULT_OUT   = _REPO_ROOT / "outputs" / "3d_object"


def load_model(ckpt: str, device: str = "cuda", pipeline_type: str = "1024_cascade"):
    from models.gen_3d_object.trellis_2_model import Trellis2Model
    print(f"[run] Loading Trellis2Model from: {ckpt}")
    return Trellis2Model(ckpt_path=ckpt, device=device, pipeline_type=pipeline_type)


def make_operator(model, output_dir: str):
    from operators.gen_3d_object.operator import Gen3DObjectOperator
    return Gen3DObjectOperator(model=model, output_dir=output_dir)


def generate(inp: dict, operator) -> dict:
    """Thin wrapper so eval.py can import and reuse."""
    return operator.run(inp)


def run_from_jsonl(tasks_path: str, operator) -> list[dict]:
    """Iterate a jsonl file and run each task."""
    results = []
    with open(tasks_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            task = json.loads(line)
            print(f"[run] task_id={task.get('task_id', '?')}  image={task.get('image_path', '?')}")
            result = generate(task, operator)
            print(f"       → glb={result['glb_path']}  ({result['elapsed_sec']}s)")
            results.append(result)
    return results


def main():
    import os

    parser = argparse.ArgumentParser(description="Run 3D object generation.")
    parser.add_argument("--ckpt",      default=os.environ.get("TRELLIS2_CKPT", DEFAULT_CKPT))
    parser.add_argument("--tasks",     default=str(DEFAULT_TASKS))
    parser.add_argument("--out-dir",   default=str(DEFAULT_OUT))
    parser.add_argument("--device",    default="cuda")
    parser.add_argument("--pipeline-type", default="1024_cascade",
                        choices=["512", "1024", "1024_cascade", "1536_cascade"])
    # Single-demo mode
    parser.add_argument("--image",     default=None, help="Path to a single image (demo mode)")
    parser.add_argument("--task-id",   default="demo")
    parser.add_argument("--seed",      type=int, default=42)
    args = parser.parse_args()

    model = load_model(args.ckpt, device=args.device, pipeline_type=args.pipeline_type)
    operator = make_operator(model, output_dir=args.out_dir)

    if args.image:
        # Single demo
        result = generate({"image_path": args.image, "task_id": args.task_id, "seed": args.seed},
                          operator)
        print(f"[run] Done: {result}")
    else:
        # Batch from jsonl
        results = run_from_jsonl(args.tasks, operator)
        summary_path = Path(args.out_dir) / "results_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[run] Wrote summary → {summary_path}")


if __name__ == "__main__":
    main()
