"""
pipeline/assets_gen/gen_tpose_image/run.py

T-pose image generation demo runner.

Loads QwenEditModel + RMBGModel (or DepthAnythingModel), injects them into
GenTPoseImageOperator, reads tasks from
test_data/test_samples/tpose_gen_collect.jsonl, and writes PNG outputs.

Usage:
    # Run all tasks in the default jsonl
    python pipeline/assets_gen/gen_tpose_image/run.py

    # Override model checkpoints
    python pipeline/assets_gen/gen_tpose_image/run.py \
        --gen-ckpt Qwen/Qwen-Image-Edit-2511 \
        --mask-ckpt briaai/RMBG-1.4

    # Run from a different jsonl
    python pipeline/assets_gen/gen_tpose_image/run.py \
        --tasks test_data/test_samples/tpose_gen_collect.jsonl \
        --out-dir outputs/tpose

    # Single demo (image only, no jsonl)
    python pipeline/assets_gen/gen_tpose_image/run.py \
        --image path/to/character.png --task-id my_test \
        --description "A cheerful anime character with a red hat."
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

# Default checkpoints — HF repo ids, downloaded on first run.
# Override via env vars or CLI flags.
DEFAULT_GEN_CKPT  = "Qwen/Qwen-Image-Edit-2511"
DEFAULT_MASK_CKPT = "briaai/RMBG-1.4"
DEFAULT_TASKS = _REPO_ROOT / "test_data" / "test_samples" / "tpose_gen_collect.jsonl"
DEFAULT_OUT   = _REPO_ROOT / "outputs" / "tpose"


def load_gen_model(ckpt: str, device: str = "cuda"):
    from models.gen_image.qwen_edit import QwenEditModel
    print(f"[run] Loading QwenEditModel from: {ckpt}")
    return QwenEditModel(model_path=ckpt, device=device)


def load_mask_model(ckpt: str, device: str = "cuda", model_type: str = "rmbg"):
    """Load the foreground / matting model. `model_type` ∈ {"rmbg", "depth"}."""
    if model_type == "depth":
        from models.tools.image_matting.depth_anything import DepthAnythingModel
        print(f"[run] Loading DepthAnythingModel from: {ckpt}")
        return DepthAnythingModel(model_path=ckpt, device=device)
    from models.tools.image_matting.rmbg import RMBGModel
    print(f"[run] Loading RMBGModel from: {ckpt}")
    return RMBGModel(model_path=ckpt, device=device)


def make_operator(gen_model, mask_model, output_dir: str):
    from operators.gen_tpose_image.operator import GenTPoseImageOperator
    return GenTPoseImageOperator(
        gen_model=gen_model,
        mask_model=mask_model,
        output_dir=output_dir,
    )


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
            print(f"       → rgba={result['tpose_rgba_path']}  ({result['elapsed_sec']}s)")
            results.append(result)
    return results


def main():
    import os

    parser = argparse.ArgumentParser(description="Run T-pose generation.")
    parser.add_argument("--gen-ckpt",  default=os.environ.get("QWEN_EDIT_CKPT", DEFAULT_GEN_CKPT))
    parser.add_argument("--mask-ckpt", default=os.environ.get("RMBG_CKPT",       DEFAULT_MASK_CKPT))
    parser.add_argument("--mask-type", default="rmbg", choices=["rmbg", "depth"])
    parser.add_argument("--tasks",     default=str(DEFAULT_TASKS))
    parser.add_argument("--out-dir",   default=str(DEFAULT_OUT))
    parser.add_argument("--device",    default="cuda")
    # Single-demo mode
    parser.add_argument("--image",       default=None, help="Path to a single image (demo mode)")
    parser.add_argument("--task-id",     default="demo")
    parser.add_argument("--description", default="")
    parser.add_argument("--seed",        type=int, default=42)
    parser.add_argument("--steps",       type=int, default=40)
    parser.add_argument("--target-size", type=int, default=1024)
    args = parser.parse_args()

    gen_model  = load_gen_model(args.gen_ckpt, device=args.device)
    mask_model = load_mask_model(args.mask_ckpt, device=args.device, model_type=args.mask_type)
    operator = make_operator(gen_model, mask_model, output_dir=args.out_dir)

    if args.image:
        result = generate(
            {
                "image_path":  args.image,
                "task_id":     args.task_id,
                "description": args.description,
                "seed":        args.seed,
                "steps":       args.steps,
                "target_size": args.target_size,
            },
            operator,
        )
        print(f"[run] Done: {result}")
    else:
        results = run_from_jsonl(args.tasks, operator)
        summary_path = Path(args.out_dir) / "results_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[run] Wrote summary → {summary_path}")


if __name__ == "__main__":
    main()
