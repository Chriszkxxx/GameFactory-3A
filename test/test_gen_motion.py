"""Tests for gen_motion and its Puppeteer motion-retarget function."""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
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

from operators.gen_motion.funcs.puppeteer_retarget.validate_mapping import (  # noqa: E402
    load_and_validate_mapping,
)
from operators.gen_motion.funcs.retarget_motion import (  # noqa: E402
    _subprocess_env as _retarget_subprocess_env,
    ensure_retarget_runtime,
    normalise_source_ext,
    retarget_motion,
)
from operators.gen_motion.metrics import evaluate  # noqa: E402
from operators.gen_motion.operator import GenMotionOperator  # noqa: E402


class MotionRetargetFixture:
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
            json.dumps(stubs.retarget_mapping(), indent=2),
            encoding="utf-8",
        )

    def task(self, *, mapping: bool = True) -> dict:
        return {
            "task_id": "retarget_unit",
            "task_type": "retarget",
            "source_motion_path": str(self.source),
            "target_glb_path": str(self.target),
            "target_rig_path": str(self.rig),
            "mapping_path": str(self.mapping) if mapping else None,
            "fps": 20,
        }


class TestGenMotionOperator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aaagf_motion_test_")
        self.root = Path(self.tmp.name)
        self.fixture = MotionRetargetFixture(self.root)
        self.retarget_fn = mock.Mock(side_effect=stubs.stub_retarget_motion)
        self.operator = GenMotionOperator(
            output_dir=str(self.root / "outputs"),
            retarget_fn=self.retarget_fn,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_explicit_mapping_writes_four_artifacts(self):
        result = self.operator.run(self.fixture.task())
        self.assertEqual(result["task_kind"], "motion")
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
            stubs.retarget_mapping()["bone_map"],
        )

    def test_missing_mapping_uses_automatic_mapping_path(self):
        result = self.operator.run(self.fixture.task(mapping=False))
        self.assertTrue(Path(result["mapping_path"]).is_file())
        self.assertIsNone(self.retarget_fn.call_args.kwargs["mapping_path"])

    def test_animation_only_can_be_disabled(self):
        task = self.fixture.task()
        task["export_anim_only"] = False
        result = self.operator.run(task)
        self.assertIsNone(result["anim_only_fbx_path"])

    def test_invalid_mapping_fails_before_function_call(self):
        self.fixture.mapping.write_text('{"bone_map": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-empty 'bone_map'"):
            self.operator.run(self.fixture.task())
        self.retarget_fn.assert_not_called()

    def test_wrong_source_extension_is_rejected(self):
        bad_source = self.root / "source.txt"
        bad_source.write_text("not motion", encoding="utf-8")
        task = self.fixture.task()
        task["source_motion_path"] = str(bad_source)
        with self.assertRaisesRegex(ValueError, r"\.bvh or \.fbx"):
            self.operator.run(task)

    def test_unknown_task_type_is_explicitly_unimplemented(self):
        task = self.fixture.task()
        task["task_type"] = "generate"
        with self.assertRaisesRegex(NotImplementedError, "Unsupported"):
            self.operator.run(task)

    def test_structural_metrics(self):
        result = self.operator.run(self.fixture.task())
        score = evaluate(result, self.fixture.task())
        self.assertTrue(score["artifact_valid"])
        self.assertTrue(score["mapping_valid"])
        self.assertEqual(score["required_chain_coverage"], 1.0)
        self.assertTrue(score["timing_preserved"])
        self.assertEqual(score["fps"], 20)


class TestGenMotionHumanStages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aaagf_humanoid_test_")
        self.root = Path(self.tmp.name)
        self.target = self.root / "avatar.glb"
        self.target.write_bytes(stubs.make_minimal_glb())
        self.puppeteer = stubs.StubPuppeteerModel()
        self.momask = stubs.StubMoMaskModel()
        self.retarget_fn = mock.Mock(side_effect=stubs.stub_retarget_motion)
        self.operator = GenMotionOperator(
            output_dir=str(self.root / "outputs"),
            puppeteer_model=self.puppeteer,
            momask_model=self.momask,
            retarget_fn=self.retarget_fn,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_rig_writes_puppeteer_artifacts_and_forwards_seed(self):
        result = self.operator.run(
            {
                "task_id": "rig_unit",
                "task_type": "rig",
                "target_glb_path": str(self.target),
                "seed": 17,
            }
        )
        self.assertIsNotNone(result["rig_path"])
        self.assertIsNotNone(result["skeleton_path"])
        self.assertIsNotNone(result["mesh_obj_path"])
        self.assertIsNone(result["motion_bvh_path"])
        self.assertIsNone(result["retargeted_fbx_path"])
        self.assertEqual(self.puppeteer.calls[0]["seed"], 17)
        self.assertEqual(self.puppeteer.calls[0]["mesh_format"], ".glb")
        score = evaluate(result, {"task_type": "rig"})
        self.assertTrue(score["artifact_valid"])
        self.assertEqual(score["joint_count"], 6)

    def test_text_to_motion_writes_native_20fps_artifacts(self):
        task = {
            "task_id": "motion_unit",
            "task_type": "text_to_motion",
            "prompt": "A person turns left.",
            "seed": 9,
            "motion_length": 40,
            "in_place": True,
        }
        result = self.operator.run(task)
        for key in (
            "motion_bvh_path",
            "raw_motion_bvh_path",
            "ik_motion_bvh_path",
            "joints_npy_path",
            "preview_mp4_path",
        ):
            self.assertTrue(Path(result[key]).is_file(), key)
        self.assertEqual(self.momask.calls[0]["seed"], 9)
        self.assertEqual(self.momask.calls[0]["motion_length"], 40)
        self.assertTrue(self.momask.calls[0]["in_place"])
        score = evaluate(result, task)
        self.assertTrue(score["artifact_valid"])
        self.assertEqual(score["motion_fps"], 20)
        self.assertEqual(score["motion_frame_count"], 2)

    def test_humanoid_runs_rig_motion_then_retarget(self):
        task = {
            "task_id": "humanoid_unit",
            "task_type": "humanoid",
            "target_glb_path": str(self.target),
            "prompt": "A person walks forward and waves.",
            "in_place": True,
        }
        result = self.operator.run(task)
        expected = (
            "rig_path",
            "skeleton_path",
            "mesh_obj_path",
            "motion_bvh_path",
            "raw_motion_bvh_path",
            "ik_motion_bvh_path",
            "joints_npy_path",
            "preview_mp4_path",
            "retargeted_fbx_path",
            "anim_only_fbx_path",
            "mapping_path",
            "retarget_info_path",
        )
        for key in expected:
            self.assertIsNotNone(result[key], key)
            self.assertTrue(Path(result[key]).is_file(), key)
        self.assertEqual(
            self.retarget_fn.call_args.kwargs["source_motion_path"],
            result["motion_bvh_path"],
        )
        self.assertEqual(self.retarget_fn.call_args.kwargs["fps"], 20)
        score = evaluate(result, task)
        self.assertTrue(score["artifact_valid"])
        self.assertTrue(score["rig_valid"])
        self.assertTrue(score["motion_valid"])
        self.assertTrue(score["retarget_valid"])

    def test_models_are_required_only_for_their_stages(self):
        operator = GenMotionOperator(
            output_dir=str(self.root / "missing"),
            retarget_fn=stubs.stub_retarget_motion,
        )
        with self.assertRaisesRegex(RuntimeError, "PuppeteerModel"):
            operator.run(
                {
                    "task_id": "missing_rig",
                    "task_type": "rig",
                    "target_glb_path": str(self.target),
                }
            )
        with self.assertRaisesRegex(RuntimeError, "MoMaskModel"):
            operator.run(
                {
                    "task_id": "missing_motion",
                    "task_type": "text_to_motion",
                    "prompt": "Walk.",
                }
            )


class TestMotionModelContracts(unittest.TestCase):
    def test_puppeteer_cpu_inference_is_rejected_before_loading(self):
        from models.gen_motion import PuppeteerModel

        model = PuppeteerModel("missing", device="cpu")
        with self.assertRaisesRegex(RuntimeError, "requires CUDA"):
            model.infer(b"mesh", mesh_format=".obj")

    def test_missing_runtime_paths_have_actionable_errors(self):
        from models.gen_motion import MoMaskModel, PuppeteerModel

        with self.assertRaisesRegex(RuntimeError, "runtime is incomplete"):
            PuppeteerModel(
                str(_REPO_ROOT / "missing_puppeteer"),
                python_bin=sys.executable,
            ).load()
        with self.assertRaisesRegex(RuntimeError, "runtime is incomplete"):
            MoMaskModel(
                str(_REPO_ROOT / "missing_momask"),
                python_bin=sys.executable,
            ).load()

    def test_puppeteer_forwards_seed_to_both_stages(self):
        from models.gen_motion import PuppeteerModel

        with tempfile.TemporaryDirectory(prefix="aaagf_puppeteer_fake_") as tmp:
            root = Path(tmp)
            for path in (
                root / "skeleton" / "demo.py",
                root
                / "skeleton"
                / "skeleton_ckpts"
                / "puppeteer_skeleton_w_diverse_pose.pth",
                root / "skinning" / "main.py",
                root
                / "skinning"
                / "skinning_ckpts"
                / "puppeteer_skin_w_diverse_pose_depth1.pth",
                root
                / "skeleton"
                / "third_partys"
                / "opt-350m"
                / "config.json",
                root
                / "skeleton"
                / "third_partys"
                / "Michelangelo"
                / "checkpoints"
                / "aligned_shape_latents"
                / "shapevae-256.ckpt",
                root
                / "skinning"
                / "third_partys"
                / "PartField"
                / "ckpt"
                / "model_objaverse.ckpt",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"stub")

            model = PuppeteerModel(
                str(root),
                python_bin=sys.executable,
            )
            commands = []

            def fake_run(command, *, cwd, stage):
                commands.append((stage, command))
                if stage == "skeleton":
                    output = Path(command[command.index("--output_dir") + 1])
                    name = command[command.index("--save_name") + 1]
                    predicted = output / name / "avatar_pred.txt"
                    predicted.parent.mkdir(parents=True, exist_ok=True)
                    predicted.write_text(
                        "joints joint0 0 0 0\nroot joint0\n",
                        encoding="utf-8",
                    )
                else:
                    output = Path(command[command.index("--save_folder") + 1])
                    rig = output / "generate" / "avatar_skin.txt"
                    rig.parent.mkdir(parents=True, exist_ok=True)
                    rig.write_text(
                        "joints joint0 0 0 0\nroot joint0\n"
                        "skin 0 joint0 1.0\n",
                        encoding="utf-8",
                    )

            with mock.patch.object(model, "_run", side_effect=fake_run):
                result = model.infer(
                    b"o Avatar\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n",
                    mesh_format=".obj",
                    seed=23,
                )
            self.assertEqual(len(commands), 2)
            for _, command in commands:
                self.assertIn("--seed", command)
                self.assertEqual(command[command.index("--seed") + 1], "23")
            self.assertEqual(
                commands[0][1][commands[0][1].index("--llm") + 1],
                "third_partys/opt-350m",
            )
            self.assertIn("--post_filter", commands[1][1])
            self.assertEqual(result["joint_count"], 1)
            self.assertEqual(result["skin_vertex_count"], 1)

    def test_momask_forwards_generation_parameters_and_cleans_output(self):
        import numpy as np

        from models.gen_motion import MoMaskModel

        with tempfile.TemporaryDirectory(prefix="aaagf_momask_fake_") as tmp:
            root = Path(tmp)
            required = (
                root / "gen_t2m.py",
                root
                / "checkpoints"
                / "t2m"
                / "t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns"
                / "opt.txt",
                root
                / "checkpoints"
                / "t2m"
                / "t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns"
                / "model"
                / "latest.tar",
                root
                / "checkpoints"
                / "t2m"
                / "tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw"
                / "opt.txt",
                root
                / "checkpoints"
                / "t2m"
                / "tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw"
                / "model"
                / "net_best_fid.tar",
                root
                / "checkpoints"
                / "t2m"
                / "rvq_nq6_dc512_nc512_noshare_qdp0.2"
                / "opt.txt",
                root
                / "checkpoints"
                / "t2m"
                / "rvq_nq6_dc512_nc512_noshare_qdp0.2"
                / "model"
                / "net_best_fid.tar",
                root
                / "checkpoints"
                / "t2m"
                / "length_estimator"
                / "model"
                / "finest.tar",
            )
            for path in required:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"stub")

            captured = {}

            def fake_subprocess(command, **_kwargs):
                captured["command"] = command
                ext = command[command.index("--ext") + 1]
                animation = root / "generation" / ext / "animations" / "0"
                joints = root / "generation" / ext / "joints" / "0"
                animation.mkdir(parents=True)
                joints.mkdir(parents=True)
                bvh = (
                    "HIERARCHY\nROOT Hips\n{\n"
                    "CHANNELS 6 Xposition Yposition Zposition "
                    "Zrotation Xrotation Yrotation\n}\n"
                    "MOTION\nFrames: 1\nFrame Time: 0.05\n"
                    "1 2 3 0 0 0\n"
                )
                (animation / "sample0_repeat0_len40.bvh").write_text(bvh)
                (animation / "sample0_repeat0_len40_ik.bvh").write_text(bvh)
                (animation / "sample0_repeat0_len40.mp4").write_bytes(b"mp4")
                (animation / "sample0_repeat0_len40_ik.mp4").write_bytes(
                    b"mp4ik"
                )
                np.save(
                    joints / "sample0_repeat0_len40.npy",
                    np.zeros((1, 22, 3), dtype=np.float32),
                )
                np.save(
                    joints / "sample0_repeat0_len40_ik.npy",
                    np.ones((1, 22, 3), dtype=np.float32),
                )
                return subprocess.CompletedProcess(command, 0, "", "")

            model = MoMaskModel(
                str(root),
                python_bin=sys.executable,
                device="cpu",
            )
            with mock.patch(
                "models.gen_motion.momask_model.subprocess.run",
                side_effect=fake_subprocess,
            ):
                result = model.infer(
                    "Walk and wave.",
                    seed=31,
                    motion_length=40,
                    cond_scale=3.5,
                    time_steps=12,
                    in_place=True,
                )
            command = captured["command"]
            expected = {
                "--seed": "31",
                "--motion_length": "40",
                "--cond_scale": "3.5",
                "--time_steps": "12",
                "--gpu_id": "-1",
            }
            for flag, value in expected.items():
                self.assertEqual(command[command.index(flag) + 1], value)
            self.assertEqual(result["fps"], 20)
            self.assertFalse(any((root / "generation").glob("aaagf_*")))


class TestRetargetFunction(unittest.TestCase):
    def test_source_extension_validation(self):
        self.assertEqual(normalise_source_ext("BVH"), ".bvh")
        self.assertEqual(normalise_source_ext(".fbx"), ".fbx")
        with self.assertRaisesRegex(ValueError, "source_ext"):
            normalise_source_ext(".glb")

    def test_missing_bpy_runtime_has_actionable_error(self):
        ensure_retarget_runtime.cache_clear()
        missing = str(_REPO_ROOT / "does_not_exist" / "python.exe")
        with self.assertRaisesRegex(
            RuntimeError,
            "AAAGF_RETARGET_BPY_PYTHON",
        ):
            ensure_retarget_runtime(missing)

    def test_mapping_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapping.json"
            path.write_text('{"bone_map": {"Hips": "joint0"}}')
            data = load_and_validate_mapping(path)
            self.assertEqual(data["bone_map"]["Hips"], "joint0")
            path.write_text('{"bone_map": []}')
            with self.assertRaisesRegex(ValueError, "bone_map"):
                load_and_validate_mapping(path)

    def test_auto_mapping_and_two_export_commands(self):
        module = importlib.import_module(
            "operators.gen_motion.funcs.retarget_motion"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = MotionRetargetFixture(root)

            def fake_run(
                _bpy_python,
                backend_module,
                _args,
                *,
                expected,
                device,
                verbose,
            ):
                self.assertEqual(device, "cpu")
                self.assertFalse(verbose)
                if backend_module.endswith("mapping_auto"):
                    expected[0].write_text(
                        json.dumps(stubs.retarget_mapping()),
                        encoding="utf-8",
                    )
                    return
                for path in expected:
                    if path.suffix == ".json":
                        path.write_text(
                            json.dumps(stubs.retarget_info(30)),
                            encoding="utf-8",
                        )
                    else:
                        path.write_bytes(
                            b"Kaydara FBX Binary  \x00" + bytes(32)
                        )

            with (
                mock.patch.object(
                    module,
                    "ensure_retarget_runtime",
                    return_value=sys.executable,
                ),
                mock.patch.object(
                    module,
                    "_run_module",
                    side_effect=fake_run,
                ) as run_module,
            ):
                result = retarget_motion(
                    bpy_python=sys.executable,
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
            modules = [
                call.args[1] for call in run_module.call_args_list
            ]
            self.assertTrue(modules[0].endswith("mapping_auto"))
            self.assertTrue(modules[1].endswith("world_delta"))
            self.assertTrue(modules[2].endswith("world_delta"))
            self.assertIn(
                "--anim-only",
                run_module.call_args_list[2].args[2],
            )
            for key in (
                "retargeted_fbx_path",
                "anim_only_fbx_path",
                "mapping_path",
                "retarget_info_path",
            ):
                self.assertTrue(Path(result[key]).is_file())


class TestGenMotionEvaluationPipeline(unittest.TestCase):
    def test_existing_artifacts_are_scored_without_generation(self):
        from pipeline.assets_gen.gen_motion.eval import evaluate_tasks
        from pipeline.common import paths

        game_id = "_motion_eval_test"
        run_id = "_test"
        with tempfile.TemporaryDirectory(prefix="aaagf_motion_eval_") as tmp:
            fixture = MotionRetargetFixture(Path(tmp))
            operator = GenMotionOperator(
                run_id=run_id,
                default_game_id=game_id,
                retarget_fn=stubs.stub_retarget_motion,
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
                        "motion",
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


_BPY_PYTHON = os.environ.get("AAAGF_RETARGET_BPY_PYTHON")


@unittest.skipUnless(
    _BPY_PYTHON,
    "Set AAAGF_RETARGET_BPY_PYTHON for the synthetic bpy integration test.",
)
class TestGenMotionSyntheticBpyIntegration(unittest.TestCase):
    """Run a generated one-bone asset through the real bpy subprocess."""

    game_id = "_motion_synthetic_integration"
    run_id = "_test"

    @classmethod
    def tearDownClass(cls):
        from pipeline.common import paths

        shutil.rmtree(paths.game_output_dir(cls.game_id), ignore_errors=True)

    def test_synthetic_pipeline(self):
        from pipeline.assets_gen.gen_motion.run import (
            generate,
            load_retarget_runtime,
            make_operator,
        )

        with tempfile.TemporaryDirectory(prefix="aaagf_motion_bpy_") as tmp:
            root = Path(tmp)
            source = root / "source.bvh"
            target = root / "target.glb"
            rig = root / "target_rig.txt"
            mapping = root / "mapping.json"

            source.write_text(
                "HIERARCHY\n"
                "ROOT Hips\n"
                "{\n"
                "  OFFSET 0 0 0\n"
                "  CHANNELS 6 Xposition Yposition Zposition "
                "Zrotation Xrotation Yrotation\n"
                "  End Site\n"
                "  {\n"
                "    OFFSET 0 1 0\n"
                "  }\n"
                "}\n"
                "MOTION\n"
                "Frames: 2\n"
                "Frame Time: 0.033333\n"
                "0 0 0 0 0 0\n"
                "0.1 0 0 5 0 0\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    str(_BPY_PYTHON),
                    "-c",
                    (
                        "import trimesh; "
                        f"trimesh.creation.box().export({str(target)!r})"
                    ),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=_retarget_subprocess_env(str(_BPY_PYTHON), "cpu"),
            )
            rig.write_text(
                "\n".join(
                    [
                        "joints joint0 0 0 0",
                        "root joint0",
                        *[f"skin {index} joint0 1.0" for index in range(8)],
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            mapping.write_text(
                json.dumps(
                    {
                        "root_bones": {
                            "source": "Hips",
                            "puppeteer": "joint0",
                        },
                        "bone_map": {"Hips": "joint0"},
                        "retarget_chains": {},
                    }
                ),
                encoding="utf-8",
            )

            runtime = load_retarget_runtime(str(_BPY_PYTHON), device="cpu")
            operator = make_operator(
                runtime,
                run_id=self.run_id,
                default_game_id=self.game_id,
            )
            result = generate(
                {
                    "game_id": self.game_id,
                    "task_id": "synthetic_retarget",
                    "task_type": "retarget",
                    "source_motion_path": str(source),
                    "target_glb_path": str(target),
                    "target_rig_path": str(rig),
                    "mapping_path": str(mapping),
                    "fps": 30,
                },
                operator,
            )
            for key in (
                "retargeted_fbx_path",
                "anim_only_fbx_path",
                "mapping_path",
                "retarget_info_path",
            ):
                path = Path(result[key])
                self.assertTrue(path.is_file(), key)
                self.assertGreater(path.stat().st_size, 0, key)
            self.assertEqual(result["task_kind"], "motion")
            self.assertTrue(
                (Path(result["output_dir"]) / "meta.json").is_file()
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
class TestGenMotionRealIntegration(unittest.TestCase):
    """Optional real bpy integration test using external, uncommitted assets."""

    game_id = "_motion_integration"
    run_id = "_test"

    @classmethod
    def tearDownClass(cls):
        from pipeline.common import paths

        shutil.rmtree(paths.game_output_dir(cls.game_id), ignore_errors=True)

    def test_real_pipeline(self):
        from pipeline.assets_gen.gen_motion.run import (
            generate,
            load_retarget_runtime,
            make_operator,
        )

        runtime = load_retarget_runtime(_REAL_ENV["bpy_python"], device="cpu")
        operator = make_operator(
            runtime,
            run_id=self.run_id,
            default_game_id=self.game_id,
        )
        task = {
            "game_id": self.game_id,
            "task_id": "real_retarget",
            "task_type": "retarget",
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


_HUMANOID_ENV = {
    "puppeteer_root": os.environ.get("AAAGF_PUPPETEER_MODEL_PATH"),
    "puppeteer_python": os.environ.get("AAAGF_PUPPETEER_PYTHON"),
    "momask_root": os.environ.get("AAAGF_MOMASK_MODEL_PATH"),
    "momask_python": os.environ.get("AAAGF_MOMASK_PYTHON"),
    "bpy_python": os.environ.get("AAAGF_RETARGET_BPY_PYTHON"),
    "target_glb": os.environ.get("AAAGF_HUMANOID_TARGET_GLB"),
}


@unittest.skipUnless(
    all(_HUMANOID_ENV.values()),
    "Set the AAAGF Puppeteer, MoMask, bpy and humanoid GLB environment "
    "variables for the complete real chain.",
)
class TestGenMotionRealHumanoidIntegration(unittest.TestCase):
    """Static GLB -> rig -> generated BVH -> FBX, using external weights."""

    game_id = "_motion_humanoid_integration"
    run_id = "_test"

    @classmethod
    def tearDownClass(cls):
        from pipeline.common import paths

        shutil.rmtree(paths.game_output_dir(cls.game_id), ignore_errors=True)

    def test_complete_humanoid_chain_and_fbx_reimport(self):
        from pipeline.assets_gen.gen_motion.run import (
            generate,
            load_momask_model,
            load_puppeteer_model,
            load_retarget_runtime,
            make_operator,
        )

        puppeteer = load_puppeteer_model(
            _HUMANOID_ENV["puppeteer_root"],
            python_bin=_HUMANOID_ENV["puppeteer_python"],
            device="cuda",
        )
        momask = load_momask_model(
            _HUMANOID_ENV["momask_root"],
            python_bin=_HUMANOID_ENV["momask_python"],
            device="cuda",
        )
        bpy_python = load_retarget_runtime(
            _HUMANOID_ENV["bpy_python"],
            device="cpu",
        )
        operator = make_operator(
            bpy_python,
            puppeteer_model=puppeteer,
            momask_model=momask,
            run_id=self.run_id,
            default_game_id=self.game_id,
        )
        try:
            result = generate(
                {
                    "game_id": self.game_id,
                    "task_id": "real_humanoid",
                    "task_type": "humanoid",
                    "target_glb_path": _HUMANOID_ENV["target_glb"],
                    "prompt": "A person walks forward and waves.",
                    "motion_length": 40,
                    "seed": 42,
                    "in_place": True,
                },
                operator,
            )
        finally:
            puppeteer.unload()
            momask.unload()

        for key in (
            "rig_path",
            "skeleton_path",
            "mesh_obj_path",
            "motion_bvh_path",
            "raw_motion_bvh_path",
            "ik_motion_bvh_path",
            "joints_npy_path",
            "preview_mp4_path",
            "retargeted_fbx_path",
            "anim_only_fbx_path",
            "mapping_path",
            "retarget_info_path",
        ):
            path = Path(result[key])
            self.assertTrue(path.is_file(), key)
            self.assertGreater(path.stat().st_size, 0, key)

        report_path = Path(result["output_dir"]) / "fbx_inspection.json"
        subprocess.run(
            [
                str(bpy_python),
                "-m",
                (
                    "operators.gen_motion.funcs.puppeteer_retarget."
                    "inspect_fbx"
                ),
                "--input",
                result["retargeted_fbx_path"],
                "--output",
                str(report_path),
            ],
            cwd=str(_REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
            env=_retarget_subprocess_env(str(bpy_python), "cpu"),
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertTrue(report["valid"])
        self.assertGreater(report["mesh_count"], 0)
        self.assertGreater(report["armature_count"], 0)
        self.assertGreater(report["action_count"], 0)
        self.assertGreater(report["keyframe_count"], 0)
        self.assertEqual(report["fps"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
