"""
test/test_cg_video_gen.py

Real-generation integration test for every task in a local JSONL file.

The selected backend is loaded once, then every JSONL task is sent through the
real gen_cg_video pipeline and each generated MP4 is verified. This is the
single real-generation test entry point for Seedance API, MiniMax H3 API, and
MiniMax H3 local checkpoints. The lightweight operator contract checks remain
in test/harness/.

Run from repo root:
    CG_VIDEO_BACKEND=minimax-h3 \
    MINIMAX_H3_RUNTIME=local \
    CG_VIDEO_CKPT=/path/to/MiniMax-H3 \
    CG_VIDEO_TEST_TASKS=/path/to/cg_tasks.jsonl \
    python test/test_cg_video_gen.py
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

# ── repo root on path ───────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
# ───────────────────────────────────────────────────────────────────────────────

BACKEND = os.environ.get("CG_VIDEO_BACKEND", "minimax-h3")
CKPT = os.environ.get("CG_VIDEO_CKPT")
TASKS_ENV = os.environ.get("CG_VIDEO_TEST_TASKS")
OUT_DIR = Path(
    os.environ.get("CG_VIDEO_TEST_OUT_DIR", _REPO_ROOT / "outputs" / "test_cg_video")
).expanduser()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class TestGenCGVideoPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TASKS_ENV:
            raise RuntimeError(
                "CG_VIDEO_TEST_TASKS must point to a local cg_tasks.jsonl"
            )

        cls.tasks_path = Path(TASKS_ENV).expanduser()
        if not cls.tasks_path.is_absolute():
            cls.tasks_path = _REPO_ROOT / cls.tasks_path
        if not cls.tasks_path.is_file():
            raise FileNotFoundError(f"CG task JSONL not found: {cls.tasks_path}")

        cls.tasks = [
            json.loads(line)
            for line in cls.tasks_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("//")
        ]
        if not cls.tasks:
            raise RuntimeError(
                f"Expected at least 1 test task in {cls.tasks_path}; found 0"
            )

        from pipeline.assets_gen.gen_cg_video.run import (
            BACKENDS,
            load_model,
            make_operator,
            resolve_ckpt,
        )

        if BACKEND not in BACKENDS:
            raise RuntimeError(
                f"Unknown CG_VIDEO_BACKEND={BACKEND!r}; choose one of "
                f"{sorted(BACKENDS)}"
            )

        ckpt = resolve_ckpt(BACKEND, CKPT)
        backend_kwargs = {}
        if BACKEND == "minimax-h3":
            backend_kwargs = {
                "runtime": os.environ.get("MINIMAX_H3_RUNTIME", "local"),
                "local_files_only": _env_bool("MINIMAX_LOCAL_FILES_ONLY"),
                "verbose": True,
            }

        cls.model = load_model(
            ckpt,
            device=os.environ.get("CG_VIDEO_DEVICE", "cuda"),
            backend=BACKEND,
            **backend_kwargs,
        )
        cls.operator = make_operator(cls.model, output_dir=str(OUT_DIR))

    @classmethod
    def tearDownClass(cls):
        model = getattr(cls, "model", None)
        if model is not None:
            model.unload()

    def test_run_all_tasks(self):
        from pipeline.assets_gen.gen_cg_video.run import run_from_jsonl

        results = run_from_jsonl(str(self.tasks_path), self.operator)

        self.assertEqual(len(results), len(self.tasks))
        for result in results:
            video = Path(result["video_path"])
            self.assertTrue(video.exists(), f"MP4 not found: {video}")
            self.assertGreater(
                video.stat().st_size, 1024, "MP4 file suspiciously small."
            )
            with video.open("rb") as stream:
                self.assertIn(
                    b"ftyp", stream.read(64), "Generated artifact is not an MP4."
                )
            self.assertGreater(result["elapsed_sec"], 0)
            print(
                f"  [ok] {result['task_id']} → {video.name}  "
                f"({result['elapsed_sec']}s)"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
