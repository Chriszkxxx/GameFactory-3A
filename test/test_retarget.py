"""Tests for the AAAGameForge Puppeteer motion-retarget chain."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_HARNESS = _REPO_ROOT / "test" / "harness"
if str(_HARNESS) not in sys.path:
    sys.path.insert(0, str(_HARNESS))

import stubs  # noqa: E402

from models.retarget.puppeteer_retarget_model import (  # noqa: E402
    PuppeteerRetargetModel,
)
from operators.retarget.funcs import load_and_validate_mapping  # noqa: E402
from operators.retarget.metrics import evaluate  # noqa: E402
from operators.retarget.operator import RetargetOperator  # noqa: E402


class RetargetFixture:
    def __init__(self, root: Path):
        self.source = root / "source.bvh"
        self.target = root / "target.glb"
        self.rig = root / "target_rig.txt"
        self.mapping = root / "mapping.json"
        self.source.write_text(
            "HIERARCHY\nROOT Hips\nMOTION\nFrames: 1\n"
            "Frame Time: 0.033333\n",
            encoding="utf-8",
        )
        self.target.write_bytes(b"glTF" + bytes(64))
        self.rig.write_text(
            "joints joint0 0 0 0\nroot joint0\n"
            "skin 0 joint0 1.0\n",
            encoding="utf-8",
        )
        self.mapping.write_text(
            json.dumps(stubs.StubRetargetModel._mapping(), indent=2),
            encoding="utf-8",
        )

    def task(self, *, mapping: bool = True) -> dict:
        return {
            "task_id": "retarget_unit",
            "source_motion_path": str(self.source),
            "target_glb_path": str(self.target),
            "target_rig_path": str(self.rig),
            "mapping_path": str(self.mapping) if mapping else None,
            "fps": 20,
        }


class TestRetargetOperator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aaagf_retarget_test_")
        self.root = Path(self.tmp.name)
        self.fixture = RetargetFixture(self.root)
        self.model = stubs.StubRetargetModel()
        self.operator = RetargetOperator(
            self.model,
            output_dir=str(self.root / "outputs"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_mapping_writes_four_artifacts(self):
        result = self.operator.run(self.fixture.task())
        self.assertEqual(result["task_kind"], "retarget")
        self.assertEqual(result["game_id"], "")
        for key in (
            "retargeted_fbx_path",
            "anim_only_fbx_path",
            "mapping_path",
            "retarget_info_path",
        ):
            path = Path(result[key])
            self.assertTrue(path.is_file(), key)
            self.assertGreater(path.stat().st_size, 0, key)
            self.assertTrue(path.name.startswith("retarget_unit"))
        self.assertEqual(
            json.loads(Path(result["mapping_path"]).read_text())["bone_map"],
            stubs.StubRetargetModel._mapping()["bone_map"],
        )

    def test_missing_mapping_uses_model_auto_path(self):
        result = self.operator.run(self.fixture.task(mapping=False))
        self.assertTrue(Path(result["mapping_path"]).is_file())
        self.assertIsNone(self.model.calls[-1]["mapping_path"])

    def test_animation_only_can_be_disabled(self):
        task = self.fixture.task()
        task["export_anim_only"] = False
        result = self.operator.run(task)
        self.assertIsNone(result["anim_only_fbx_path"])

    def test_invalid_mapping_fails_before_model_call(self):
        self.fixture.mapping.write_text('{"bone_map": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-empty 'bone_map'"):
            self.operator.run(self.fixture.task())
        self.assertEqual(self.model.calls, [])

    def test_wrong_source_extension_is_rejected(self):
        bad_source = self.root / "source.txt"
        bad_source.write_text("not motion", encoding="utf-8")
        task = self.fixture.task()
        task["source_motion_path"] = str(bad_source)
        with self.assertRaisesRegex(ValueError, r"\.bvh or \.fbx"):
            self.operator.run(task)

    def test_structural_metrics(self):
        result = self.operator.run(self.fixture.task())
        score = evaluate(result, self.fixture.task())
        self.assertTrue(score["artifact_valid"])
        self.assertTrue(score["mapping_valid"])
        self.assertEqual(score["required_chain_coverage"], 1.0)
        self.assertTrue(score["timing_preserved"])
        self.assertEqual(score["fps"], 20)


class TestRetargetModelContract(unittest.TestCase):
    def test_memory_infer_returns_stable_artifact_dict(self):
        model = PuppeteerRetargetModel(
            model_path=sys.executable,
            device="cpu",
        )

        def fake_save(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"full-fbx")
            Path(kwargs["anim_only_output_path"]).write_bytes(b"anim-fbx")
            Path(kwargs["mapping_output_path"]).write_text(
                json.dumps(stubs.StubRetargetModel._mapping()),
                encoding="utf-8",
            )
            Path(kwargs["info_output_path"]).write_text(
                json.dumps(stubs.StubRetargetModel._info(30)),
                encoding="utf-8",
            )
            return {}

        with mock.patch.object(
            model,
            "infer_and_save",
            side_effect=fake_save,
        ):
            result = model.infer(
                b"source",
                ".bvh",
                b"target",
                "rig",
                stubs.StubRetargetModel._mapping(),
            )
        self.assertEqual(result["retargeted_fbx"], b"full-fbx")
        self.assertEqual(result["anim_only_fbx"], b"anim-fbx")
        self.assertIsInstance(result["mapping"], dict)
        self.assertIsInstance(result["retarget_info"], dict)

    def test_source_extension_validation(self):
        self.assertEqual(
            PuppeteerRetargetModel._normalise_source_ext("BVH"),
            ".bvh",
        )
        self.assertEqual(
            PuppeteerRetargetModel._normalise_source_ext(".fbx"),
            ".fbx",
        )
        with self.assertRaisesRegex(ValueError, "source_ext"):
            PuppeteerRetargetModel._normalise_source_ext(".glb")

    def test_missing_bpy_runtime_has_actionable_error(self):
        model = PuppeteerRetargetModel(
            model_path=str(_REPO_ROOT / "does_not_exist" / "python.exe"),
            device="cpu",
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "AAAGF_RETARGET_BPY_PYTHON",
        ):
            model._ensure_runtime()

    def test_mapping_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapping.json"
            path.write_text('{"bone_map": {"Hips": "joint0"}}')
            PuppeteerRetargetModel._validate_mapping_file(path)
            path.write_text('{"bone_map": []}')
            with self.assertRaisesRegex(ValueError, "bone_map"):
                PuppeteerRetargetModel._validate_mapping_file(path)

    def test_operator_mapping_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapping.json"
            path.write_text('{"bone_map": {"Hips": "joint0"}}')
            data = load_and_validate_mapping(path)
            self.assertEqual(data["bone_map"]["Hips"], "joint0")

    def test_auto_mapping_and_two_export_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = RetargetFixture(root)
            model = PuppeteerRetargetModel(
                model_path=sys.executable,
                device="cpu",
            )
            model._runtime_checked = True

            def fake_run(module, args, *, expected):
                if module.endswith("mapping_auto"):
                    expected[0].write_text(
                        json.dumps(stubs.StubRetargetModel._mapping()),
                        encoding="utf-8",
                    )
                    return
                for path in expected:
                    if path.suffix == ".json":
                        path.write_text(
                            json.dumps(
                                stubs.StubRetargetModel._info(30)
                            ),
                            encoding="utf-8",
                        )
                    else:
                        path.write_bytes(
                            b"Kaydara FBX Binary  \x00" + bytes(32)
                        )

            with mock.patch.object(
                model,
                "_run_module",
                side_effect=fake_run,
            ) as run_module:
                result = model.infer_and_save(
                    source_motion_path=str(fixture.source),
                    target_glb_path=str(fixture.target),
                    target_rig_path=str(fixture.rig),
                    output_path=str(root / "retargeted.fbx"),
                    anim_only_output_path=str(root / "animation.fbx"),
                    mapping_path=None,
                    mapping_output_path=str(root / "mapping_out.json"),
                    info_output_path=str(root / "retarget_info.json"),
                )

            self.assertEqual(run_module.call_count, 3)
            modules = [call.args[0] for call in run_module.call_args_list]
            self.assertTrue(modules[0].endswith("mapping_auto"))
            self.assertTrue(modules[1].endswith("world_delta"))
            self.assertTrue(modules[2].endswith("world_delta"))
            self.assertIn(
                "--anim-only",
                run_module.call_args_list[2].args[1],
            )
            for key in (
                "retargeted_fbx_path",
                "anim_only_fbx_path",
                "mapping_path",
                "retarget_info_path",
            ):
                self.assertTrue(Path(result[key]).is_file())


class TestRetargetEvaluationPipeline(unittest.TestCase):
    def test_existing_artifacts_are_scored_without_generation(self):
        from pipeline.assets_gen.retarget.eval import evaluate_tasks
        from pipeline.common import paths

        game_id = "_retarget_eval_test"
        run_id = "_test"
        with tempfile.TemporaryDirectory(prefix="aaagf_retarget_eval_") as tmp:
            fixture = RetargetFixture(Path(tmp))
            model = stubs.StubRetargetModel()
            operator = RetargetOperator(
                model,
                run_id=run_id,
                default_game_id=game_id,
            )
            task = {
                **fixture.task(),
                "game_id": game_id,
                "task_id": "eval_task",
            }
            operator.run(task)
            tasks_path = Path(tmp) / "tasks.jsonl"
            tasks_path.write_text(json.dumps(task) + "\n", encoding="utf-8")
            try:
                scores = evaluate_tasks(
                    str(tasks_path),
                    game_filter=game_id,
                    run_id=run_id,
                )
                self.assertEqual(len(scores), 1)
                self.assertTrue(scores[0]["artifact_valid"])
                metrics_path = (
                    paths.eval_output_dir(
                        game_id,
                        "retarget",
                        "eval_task",
                        run_id=run_id,
                        create=False,
                    )
                    / "metrics.json"
                )
                self.assertTrue(metrics_path.is_file())
            finally:
                shutil.rmtree(
                    paths.game_output_dir(game_id),
                    ignore_errors=True,
                )


_REAL_ENV = {
    "bpy_python": os.environ.get("AAAGF_RETARGET_BPY_PYTHON"),
    "source_motion": os.environ.get("AAAGF_RETARGET_SOURCE_MOTION"),
    "target_glb": os.environ.get("AAAGF_RETARGET_TARGET_GLB"),
    "target_rig": os.environ.get("AAAGF_RETARGET_TARGET_RIG"),
}
_REAL_READY = all(_REAL_ENV.values())


@unittest.skipUnless(
    _REAL_READY,
    "Set AAAGF_RETARGET_BPY_PYTHON, AAAGF_RETARGET_SOURCE_MOTION, "
    "AAAGF_RETARGET_TARGET_GLB and AAAGF_RETARGET_TARGET_RIG for the real test.",
)
class TestRetargetRealIntegration(unittest.TestCase):
    """Optional real bpy integration test using external, uncommitted assets."""

    game_id = "_retarget_integration"
    run_id = "_test"

    @classmethod
    def tearDownClass(cls):
        from pipeline.common import paths

        shutil.rmtree(paths.game_output_dir(cls.game_id), ignore_errors=True)

    def test_real_pipeline(self):
        from pipeline.assets_gen.retarget.run import (
            generate,
            load_model,
            make_operator,
        )

        model = load_model(_REAL_ENV["bpy_python"], device="cpu")
        operator = make_operator(
            model,
            run_id=self.run_id,
            default_game_id=self.game_id,
        )
        task = {
            "game_id": self.game_id,
            "task_id": "real_retarget",
            "source_motion_path": _REAL_ENV["source_motion"],
            "target_glb_path": _REAL_ENV["target_glb"],
            "target_rig_path": _REAL_ENV["target_rig"],
            "mapping_path": os.environ.get("AAAGF_RETARGET_MAPPING"),
            "fps": int(os.environ.get("AAAGF_RETARGET_FPS", "30")),
        }
        result = generate(task, operator)
        for key in (
            "retargeted_fbx_path",
            "anim_only_fbx_path",
            "mapping_path",
            "retarget_info_path",
        ):
            path = Path(result[key])
            self.assertTrue(path.is_file(), key)
            self.assertGreater(path.stat().st_size, 0, key)
        self.assertTrue((Path(result["output_dir"]) / "meta.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
