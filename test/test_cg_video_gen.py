"""Offline local-model tests for the CG video generation slot.

This mirrors ``test_3d_object_gen.py`` at the task level while replacing the
large local pipelines with small runtime doubles. No network, weights or GPU
are required.
"""

from __future__ import annotations

import io
import inspect
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from models.gen_cg_video import (  # noqa: E402
    MiniMaxH3Model,
    SeedanceModel,
    VideoGenerationInput,
    VideoGenerationMode,
)
from models.gen_cg_video.minimax_h3_model import (  # noqa: E402
    AUDIO_VAE,
    DEFAULT_LOCAL_MODEL,
    FL2VA_MODEL,
    REF2VA_MODEL,
    TEXT_ENCODER,
    VIDEO_VAE,
    _ComfyMiniMaxRuntime,
    _aligned_frame_count,
)

MP4 = b"\x00\x00\x00\x18ftypmp42aaagf-cg-video-test"
LOCAL_WEIGHTS = (FL2VA_MODEL, REF2VA_MODEL, TEXT_ENCODER, VIDEO_VAE, AUDIO_VAE)


def write_local_minimax_tree(root: Path, *, include_ref: bool = True) -> None:
    for relative_path in LOCAL_WEIGHTS:
        if relative_path == REF2VA_MODEL and not include_ref:
            continue
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stub")


def request(mode: VideoGenerationMode, *, duration: float = 6) -> VideoGenerationInput:
    images = {}
    if mode is VideoGenerationMode.FIRST_FRAME_TO_VIDEO:
        images["first_frame"] = Image.new("RGB", (320, 320), "red")
    elif mode is VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO:
        images["first_frame"] = Image.new("RGB", (320, 320), "red")
        images["last_frame"] = Image.new("RGB", (320, 320), "blue")
    elif mode is VideoGenerationMode.REFERENCE_TO_VIDEO:
        images["reference_images"] = (Image.new("RGB", (320, 320), "green"),)
    return VideoGenerationInput(
        mode=mode,
        prompt="A cinematic camera move.",
        duration_sec=duration,
        seed=7,
        **images,
    )


class FakeMiniMaxLocalRuntime:
    def __init__(self):
        self.calls: list[tuple[VideoGenerationInput, object, dict]] = []
        self.unloaded = False
        self.torch = SimpleNamespace(inference_mode=lambda: nullcontext())

    def generate(self, request, output, **kwargs):
        self.calls.append((request, output, kwargs))
        if hasattr(output, "write"):
            output.write(MP4)
        else:
            Path(output).write_bytes(MP4)

    def unload(self):
        self.unloaded = True


def make_local_minimax(tmp: str) -> tuple[MiniMaxH3Model, FakeMiniMaxLocalRuntime]:
    root = Path(tmp)
    weights = root / "weights"
    weights.mkdir()
    write_local_minimax_tree(weights)
    model = MiniMaxH3Model(
        model_path=str(weights),
        runtime="local",
    )
    runtime = FakeMiniMaxLocalRuntime()
    model._local_runtime = runtime
    return model, runtime


class TestCGVideoModelSlot(unittest.TestCase):
    def test_minimax_signatures_match_seedance(self):
        for method in ("infer", "infer_and_save"):
            expected = str(inspect.signature(getattr(SeedanceModel, method)))
            self.assertEqual(
                str(inspect.signature(getattr(MiniMaxH3Model, method))),
                expected,
            )

    def test_runner_wires_minimax_without_loading_weights(self):
        from pipeline.assets_gen.gen_cg_video.run import load_model

        minimax = load_model(
            "unused/minimax-weights", backend="minimax-h3", runtime="local"
        )
        self.assertIsInstance(minimax, MiniMaxH3Model)
        self.assertEqual(minimax.runtime, "local")


class TestMiniMaxLocal(unittest.TestCase):
    def test_default_local_repo_is_official_comfy_org_release(self):
        model = MiniMaxH3Model(runtime="local")
        self.assertEqual(DEFAULT_LOCAL_MODEL, "Comfy-Org/MiniMax-H3")
        self.assertEqual(model.model_path, DEFAULT_LOCAL_MODEL)
        self.assertEqual(MiniMaxH3Model(runtime="local", device="cpu").device, "cpu")
        self.assertEqual(
            MiniMaxH3Model(model_path="minimax-h3", runtime="local").model_path,
            DEFAULT_LOCAL_MODEL,
        )

    def test_auto_runtime_distinguishes_api_aliases_and_local_sources(self):
        self.assertEqual(MiniMaxH3Model(model_path="hailuo-2.3").runtime, "api")
        self.assertEqual(
            MiniMaxH3Model(model_path="owner/quantized-h3").runtime, "local"
        )
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(MiniMaxH3Model(model_path=tmp).runtime, "local")

    def test_supports_all_shared_generation_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, runtime = make_local_minimax(tmp)
            for mode in VideoGenerationMode:
                out = Path(tmp) / f"{mode.value}.mp4"
                with self.subTest(mode=mode):
                    returned = model.infer_and_save(request(mode), str(out))
                    self.assertEqual(returned, str(out))
                    self.assertEqual(out.read_bytes(), MP4)
            self.assertEqual(
                [call[0].mode for call in runtime.calls], list(VideoGenerationMode)
            )
            self.assertEqual(
                runtime.calls[0][2]["files"]["diffusion_model"].name,
                Path(FL2VA_MODEL).name,
            )
            self.assertEqual(
                runtime.calls[-1][2]["files"]["diffusion_model"].name,
                Path(REF2VA_MODEL).name,
            )
            self.assertEqual(runtime.calls[-1][2]["steps"], 20)
            self.assertEqual(runtime.calls[-1][2]["scheduler"], "simple")
            self.assertEqual(runtime.calls[-1][2]["sampler_name"], "res_multistep")
            self.assertEqual(model.last_call_info["runtime"], "local")

    def test_infer_returns_mp4_bytes_without_constructing_an_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, _runtime = make_local_minimax(tmp)
            self.assertEqual(
                model.infer(request(VideoGenerationMode.TEXT_TO_VIDEO)), MP4
            )

    def test_hugging_face_download_is_lazy_per_partition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_minimax_tree(root)
            model = MiniMaxH3Model(
                model_path="owner/weights",
                runtime="local",
            )
            calls = []

            def download(repo_id, *, mode):
                calls.append((repo_id, mode))
                return root

            model._snapshot_download = download
            model._prepare_local_files(VideoGenerationMode.TEXT_TO_VIDEO)
            model._prepare_local_files(VideoGenerationMode.FIRST_FRAME_TO_VIDEO)
            model._prepare_local_files(VideoGenerationMode.REFERENCE_TO_VIDEO)
            self.assertEqual(
                calls,
                [
                    ("owner/weights", VideoGenerationMode.TEXT_TO_VIDEO),
                    ("owner/weights", VideoGenerationMode.REFERENCE_TO_VIDEO),
                ],
            )

    def test_snapshot_download_uses_only_exact_official_mode_files(self):
        calls = []

        def snapshot_download(**kwargs):
            calls.append(kwargs)
            return "/tmp/fake-minimax-snapshot"

        previous = sys.modules.get("huggingface_hub")
        sys.modules["huggingface_hub"] = SimpleNamespace(
            snapshot_download=snapshot_download
        )
        try:
            model = MiniMaxH3Model(
                model_path=DEFAULT_LOCAL_MODEL,
                runtime="local",
                hf_revision="verified-revision",
            )
            model._snapshot_download(
                DEFAULT_LOCAL_MODEL,
                mode=VideoGenerationMode.TEXT_TO_VIDEO,
            )
            model._snapshot_download(
                DEFAULT_LOCAL_MODEL,
                mode=VideoGenerationMode.REFERENCE_TO_VIDEO,
            )
        finally:
            if previous is None:
                del sys.modules["huggingface_hub"]
            else:
                sys.modules["huggingface_hub"] = previous

        self.assertEqual(
            calls[0]["allow_patterns"],
            [FL2VA_MODEL, TEXT_ENCODER, VIDEO_VAE, AUDIO_VAE],
        )
        self.assertEqual(
            calls[1]["allow_patterns"],
            [REF2VA_MODEL, TEXT_ENCODER, VIDEO_VAE, AUDIO_VAE],
        )
        for call in calls:
            self.assertEqual(call["repo_id"], DEFAULT_LOCAL_MODEL)
            self.assertEqual(call["revision"], "verified-revision")
            self.assertNotIn("ignore_patterns", call)

    def test_complete_local_tree_needs_no_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_minimax_tree(root, include_ref=False)
            model = MiniMaxH3Model(model_path=tmp, runtime="local")

            def unexpected_download(*args, **kwargs):
                raise AssertionError("complete local tree should not download")

            model._snapshot_download = unexpected_download
            files = model._prepare_local_files(VideoGenerationMode.TEXT_TO_VIDEO)
            self.assertEqual(files["diffusion_model"], (root / FL2VA_MODEL).resolve())

    def test_comfyui_source_tree_layout_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_minimax_tree(root / "models", include_ref=False)
            model = MiniMaxH3Model(model_path=tmp, runtime="local")
            files = model._prepare_local_files(VideoGenerationMode.TEXT_TO_VIDEO)
            self.assertEqual(
                files["diffusion_model"],
                (root / "models" / FL2VA_MODEL).resolve(),
            )

    def test_local_tree_requires_the_exact_mode_partition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_minimax_tree(root, include_ref=False)
            model = MiniMaxH3Model(model_path=tmp, runtime="local")
            with self.assertRaisesRegex(FileNotFoundError, "ref2va_pruned_int8"):
                model._prepare_local_files(VideoGenerationMode.REFERENCE_TO_VIDEO)

    def test_duration_uses_official_24fps_17k_plus_5_grid(self):
        self.assertEqual(_aligned_frame_count(5), 124)
        self.assertEqual(_aligned_frame_count(6), 158)

    def test_native_loaders_preserve_int8_and_minimax_types(self):
        calls = []

        class FolderPaths:
            @staticmethod
            def add_model_folder_path(category, path, is_default=False):
                calls.append(("folder", category, path, is_default))

        class UNETLoader:
            def load_unet(self, name, weight_dtype):
                calls.append(("unet", name, weight_dtype))
                return ("model",)

        class CLIPLoader:
            def load_clip(self, name, type, device):
                calls.append(("clip", name, type, device))
                return ("clip",)

        class VAELoader:
            def load_vae(self, name):
                calls.append(("vae", name))
                return (name,)

        runtime = _ComfyMiniMaxRuntime.__new__(_ComfyMiniMaxRuntime)
        runtime.folder_paths = FolderPaths
        runtime.nodes = SimpleNamespace(
            UNETLoader=UNETLoader,
            CLIPLoader=CLIPLoader,
            VAELoader=VAELoader,
        )
        runtime._models = {}
        runtime._clip_path = None
        runtime._clip = None
        runtime._video_vae_path = None
        runtime._video_vae = None
        runtime._audio_vae_path = None
        runtime._audio_vae = None

        root = Path("/models/MiniMax-H3")
        files = {
            "diffusion_model": root / FL2VA_MODEL,
            "text_encoder": root / TEXT_ENCODER,
            "video_vae": root / VIDEO_VAE,
            "audio_vae": root / AUDIO_VAE,
        }
        runtime._load_components(files)
        runtime._load_components(files)

        self.assertIn(
            ("unet", Path(FL2VA_MODEL).name, "default"),
            calls,
        )
        self.assertIn(
            ("clip", Path(TEXT_ENCODER).name, "minimax", "default"),
            calls,
        )
        self.assertEqual(sum(call[0] == "unet" for call in calls), 1)
        self.assertEqual(sum(call[0] == "clip" for call in calls), 1)
        self.assertEqual(sum(call[0] == "vae" for call in calls), 2)

    def test_native_workflow_routes_fl2v_and_r2v_through_official_nodes(self):
        calls = []

        class ImageToVideo:
            @classmethod
            def execute(cls, **kwargs):
                calls.append(("fl2v", kwargs))
                return ("positive", "latent")

        class ReferenceToVideo:
            @classmethod
            def execute(cls, **kwargs):
                calls.append(("r2v", kwargs))
                return ("positive", "latent")

        class RandomNoise:
            execute = staticmethod(lambda seed: (f"noise:{seed}",))

        class BasicGuider:
            execute = staticmethod(lambda model, positive: ("guider",))

        class KSamplerSelect:
            execute = staticmethod(lambda name: (f"sampler:{name}",))

        class BasicScheduler:
            @staticmethod
            def execute(model, scheduler, steps, denoise):
                calls.append(("scheduler", scheduler, steps, denoise))
                return ("sigmas",)

        class SamplerCustomAdvanced:
            execute = staticmethod(lambda *args: ("sampled", "denoised"))

        class VAEDecode:
            def decode(self, vae, samples):
                return ("frames",)

        class VAEDecodeAudio:
            execute = staticmethod(lambda vae, samples: ("audio",))

        class Video:
            @staticmethod
            def save_to(output):
                output.write(MP4)

        class CreateVideo:
            execute = staticmethod(lambda **kwargs: (Video(),))

        runtime = _ComfyMiniMaxRuntime.__new__(_ComfyMiniMaxRuntime)
        runtime._load_components = lambda files: (
            "model",
            "clip",
            "video_vae",
            "audio_vae",
        )
        runtime.image = lambda value: f"tensor:{value.getpixel((0, 0))}"
        runtime.MiniMaxH3ImageToVideo = ImageToVideo
        runtime.MiniMaxH3ReferenceToVideo = ReferenceToVideo
        runtime.RandomNoise = RandomNoise
        runtime.BasicGuider = BasicGuider
        runtime.KSamplerSelect = KSamplerSelect
        runtime.BasicScheduler = BasicScheduler
        runtime.SamplerCustomAdvanced = SamplerCustomAdvanced
        runtime.nodes = SimpleNamespace(VAEDecode=VAEDecode)
        runtime.VAEDecodeAudio = VAEDecodeAudio
        runtime.CreateVideo = CreateVideo

        for mode in (
            VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO,
            VideoGenerationMode.REFERENCE_TO_VIDEO,
        ):
            output = io.BytesIO()
            runtime.generate(
                request(mode),
                output,
                files={},
                width=864,
                height=480,
                fps=24,
                steps=20,
                scheduler="simple",
                sampler_name="res_multistep",
                ref_image_size="match",
            )
            self.assertEqual(output.getvalue(), MP4)

        fl2v = next(call[1] for call in calls if call[0] == "fl2v")
        r2v = next(call[1] for call in calls if call[0] == "r2v")
        self.assertEqual(fl2v["length"], 158)
        self.assertIsNotNone(fl2v["first_frame"])
        self.assertIsNotNone(fl2v["last_frame"])
        self.assertEqual(list(r2v["ref_images"]), ["ref_image_0"])
        self.assertEqual(
            [call for call in calls if call[0] == "scheduler"],
            [("scheduler", "simple", 20, 1.0)] * 2,
        )

    def test_unload_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            model, runtime = make_local_minimax(tmp)
            model.unload()
            model.unload()
            self.assertTrue(runtime.unloaded)
            self.assertIsNone(model._local_runtime)


if __name__ == "__main__":
    unittest.main(verbosity=2)
