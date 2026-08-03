"""Evaluate already-generated AudioGen WAV assets without loading generation models."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.common import paths  # noqa: E402

TASK_KIND = "audio"
AUDIO_FILENAME = "audio.wav"


def evaluate_from_jsonl(
    tasks_path: str,
    run_id: str = paths.DEFAULT_RUN_ID,
    game_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Read generated WAVs, write per-task metrics, and return score records."""
    from operators.gen_audio.operator import GenAudioOperator

    operator = GenAudioOperator()
    records: list[dict[str, Any]] = []
    for task, game_id in paths.iter_tasks(tasks_path, game_filter=game_filter):
        task_id = str(task.get("task_id", ""))
        task_dir = paths.task_output_dir(
            game_id, TASK_KIND, task_id, run_id=run_id, create=False
        )
        result = {
            "task_id": task_id,
            "game_id": game_id,
            "task_kind": TASK_KIND,
            "output_dir": str(task_dir),
            "audio_path": str(task_dir / AUDIO_FILENAME),
        }
        try:
            metrics = operator.eval(result, task)
        except Exception as exc:
            metrics = {"valid_audio": 0.0, "error": str(exc)}
        eval_dir = paths.eval_output_dir(game_id, TASK_KIND, task_id, run_id=run_id)
        metrics_path = eval_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
        record = {
            "game_id": game_id,
            "task_id": task_id,
            "audio_type": task.get("audio_type"),
            "metrics": metrics,
            "metrics_path": str(metrics_path),
        }
        records.append(record)
        print(f"[eval] game={game_id}  task_id={task_id}  valid={metrics.get('valid_audio', 0.0)}")
    return records


def write_eval_summaries(records: list[dict[str, Any]], run_id: str) -> list[Path]:
    """Write one aggregate AudioGen evaluation summary per game."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["game_id"], []).append(record)

    written = []
    for game_id, items in grouped.items():
        numeric: dict[str, list[float]] = {}
        for item in items:
            for name, value in item["metrics"].items():
                if isinstance(value, (int, float)):
                    numeric.setdefault(name, []).append(float(value))
        summary = {
            "task_kind": TASK_KIND,
            "task_count": len(items),
            "mean": {
                name: round(sum(values) / len(values), 6)
                for name, values in sorted(numeric.items())
                if values
            },
            "tasks": items,
        }
        summary_path = paths.eval_summary_path(game_id, run_id)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        written.append(summary_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate existing AudioGen artifacts.")
    parser.add_argument("--game", default=None,
                        help=f"Game project id. Known: {paths.list_games() or '<none>'}")
    parser.add_argument("--tasks", default=None)
    parser.add_argument("--run-id", default=paths.DEFAULT_RUN_ID)
    args = parser.parse_args()

    tasks_path = paths.resolve_tasks_path(TASK_KIND, args.tasks, args.game)
    records = evaluate_from_jsonl(str(tasks_path), args.run_id, args.game)
    if not records:
        print("[eval] No matching tasks — nothing to do.")
        return
    for summary_path in write_eval_summaries(records, args.run_id):
        print(f"[eval] Wrote summary -> {paths.rel_to_repo(summary_path)}")


if __name__ == "__main__":
    main()
