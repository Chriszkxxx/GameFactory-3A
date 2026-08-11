"""CG-video cloud API contract tests and opt-in paid live checks.

Offline contract cases replace HTTP with fake transports. Paid Seedance and
MiniMax checks are skipped during normal discovery so CI cannot spend credits.
Opt in to Seedance explicitly:

    export ARK_API_KEY="your-key"
    export AAAGF_RUN_SEEDANCE_LIVE=1
    export SEEDANCE_LIVE_MODES="text_to_video"
    python -m unittest test.test_api_cg_video -v

To exercise every supported mode, provide local input images and select all
four modes (multiple reference paths are separated with the platform path
separator, ``:`` on macOS/Linux and ``;`` on Windows):

    export SEEDANCE_LIVE_MODES="text_to_video,first_frame_to_video,first_last_frame_to_video,reference_to_video"
    export SEEDANCE_FIRST_FRAME="/absolute/path/to/first.png"
    export SEEDANCE_LAST_FRAME="/absolute/path/to/last.png"
    export SEEDANCE_REFERENCE_IMAGES="/absolute/ref-a.png:/absolute/ref-b.png"
    python -m unittest test.test_api_cg_video -v

The first identical request reaches Seedance; later runs reuse the response
cache to avoid being billed twice. Set ``AAAGF_SEEDANCE_DISABLE_CACHE=1`` only
when a fresh provider request is intentionally required.

MiniMax live check:

    export MINIMAX_API_KEY="your-key"
    export AAAGF_RUN_MINIMAX_LIVE=1
    export MINIMAX_LIVE_MODES="text_to_video"
    python -m unittest test.test_api_cg_video.TestMiniMaxLive -v
"""
from __future__ import annotations

import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from models.common import cloud_api  # noqa: E402
from models.gen_cg_video import (  # noqa: E402
    MiniMaxH3Model,
    SeedanceModel,
    VideoGenerationInput,
    VideoGenerationMode,
)

MP4 = b"\x00\x00\x00\x18ftypmp42aaagf-cg-video-test"

_RUN_SEEDANCE_LIVE = os.environ.get("AAAGF_RUN_SEEDANCE_LIVE") == "1"
_DEFAULT_MODE = VideoGenerationMode.TEXT_TO_VIDEO.value
_SEEDANCE_MODES = {
    value.strip()
    for value in os.environ.get("SEEDANCE_LIVE_MODES", _DEFAULT_MODE).split(",")
    if value.strip()
}


def _seedance_live_mode(mode: VideoGenerationMode):
    """Skip a paid test unless both global opt-in and mode opt-in are present."""

    enabled = _RUN_SEEDANCE_LIVE and mode.value in _SEEDANCE_MODES
    reason = (
        f"paid Seedance live check disabled; set AAAGF_RUN_SEEDANCE_LIVE=1 "
        f"and include {mode.value!r} in SEEDANCE_LIVE_MODES"
    )
    return unittest.skipUnless(enabled, reason)


def _env_image(name: str) -> Image.Image:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be an absolute local image path")
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError(f"{name} does not point to an existing absolute file: {path}")
    with Image.open(path) as image:
        return image.convert("RGB").copy()


def _reference_images() -> tuple[Image.Image, ...]:
    value = os.environ.get("SEEDANCE_REFERENCE_IMAGES", "")
    paths = [Path(item).expanduser() for item in value.split(os.pathsep) if item]
    if not paths:
        raise RuntimeError(
            "SEEDANCE_REFERENCE_IMAGES must contain at least one absolute image path"
        )

    images: list[Image.Image] = []
    for path in paths:
        if not path.is_absolute() or not path.is_file():
            raise RuntimeError(
                "SEEDANCE_REFERENCE_IMAGES contains a missing or non-absolute path: "
                f"{path}"
            )
        with Image.open(path) as image:
            images.append(image.convert("RGB").copy())
    return tuple(images)


class TestSeedanceLive(unittest.TestCase):
    """Submit, poll, download and save against the real Seedance endpoint."""

    @classmethod
    def setUpClass(cls) -> None:
        if not _RUN_SEEDANCE_LIVE:
            raise unittest.SkipTest(
                "paid Seedance checks require AAAGF_RUN_SEEDANCE_LIVE=1"
            )
        if not os.environ.get("ARK_API_KEY"):
            raise RuntimeError(
                "ARK_API_KEY is required when AAAGF_RUN_SEEDANCE_LIVE=1"
            )

        cls.output_dir = Path(
            os.environ.get(
                "SEEDANCE_OUTPUT_DIR",
                str(Path(tempfile.gettempdir()) / "aaagf_seedance_live"),
            )
        ).expanduser()
        cls.output_dir.mkdir(parents=True, exist_ok=True)

        disable_cache = os.environ.get("AAAGF_SEEDANCE_DISABLE_CACHE") == "1"
        cache_dir = None if disable_cache else str(cls.output_dir / "cache")
        cls.duration = float(os.environ.get("SEEDANCE_DURATION_SEC", "5"))
        cls.seed = int(os.environ.get("SEEDANCE_SEED", "42"))
        cls.prompt = os.environ.get(
            "SEEDANCE_PROMPT",
            "A small paper dragon flies slowly above misty mountains, cinematic lighting.",
        )
        cls.model = SeedanceModel(
            model_path=os.environ.get(
                "SEEDANCE_MODEL", "doubao-seedance-2-0-260128"
            ),
            timeout=int(os.environ.get("SEEDANCE_TASK_TIMEOUT", "1800")),
            poll_interval=float(os.environ.get("SEEDANCE_POLL_INTERVAL", "3")),
            cache_dir=cache_dir,
            resolution=os.environ.get("SEEDANCE_RESOLUTION", "720p"),
            ratio=os.environ.get("SEEDANCE_RATIO", "16:9"),
            generate_audio=os.environ.get("SEEDANCE_GENERATE_AUDIO", "0") == "1",
            watermark=os.environ.get("SEEDANCE_WATERMARK", "0") == "1",
            verbose=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        model = getattr(cls, "model", None)
        if model is not None:
            model.unload()

    def _request(
        self,
        mode: VideoGenerationMode,
        **images,
    ) -> VideoGenerationInput:
        return VideoGenerationInput(
            mode=mode,
            prompt=self.prompt,
            duration_sec=self.duration,
            seed=self.seed,
            **images,
        )

    def _run_and_verify(self, request: VideoGenerationInput) -> None:
        output = self.output_dir / f"{request.mode.value}.mp4"
        returned = self.model.infer_and_save(request, output_path=str(output))

        self.assertEqual(returned, str(output))
        self.assertTrue(output.is_file())
        self.assertGreater(output.stat().st_size, 0)
        with output.open("rb") as stream:
            self.assertIn(b"ftyp", stream.read(64), "download is not an MP4 file")

        info = self.model.last_call_info
        self.assertEqual(info["provider"], "seedance")
        self.assertEqual(info["mode"], request.mode.value)
        self.assertEqual(info["bytes"], output.stat().st_size)
        if not info["cached"]:
            self.assertTrue(info.get("task_id"))

        print(f"Seedance live artifact: {output}")
        print(f"Seedance call info: {info}")

    @_seedance_live_mode(VideoGenerationMode.TEXT_TO_VIDEO)
    def test_text_to_video(self) -> None:
        self._run_and_verify(self._request(VideoGenerationMode.TEXT_TO_VIDEO))

    @_seedance_live_mode(VideoGenerationMode.FIRST_FRAME_TO_VIDEO)
    def test_first_frame_to_video(self) -> None:
        self._run_and_verify(self._request(
            VideoGenerationMode.FIRST_FRAME_TO_VIDEO,
            first_frame=_env_image("SEEDANCE_FIRST_FRAME"),
        ))

    @_seedance_live_mode(VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO)
    def test_first_last_frame_to_video(self) -> None:
        self._run_and_verify(self._request(
            VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO,
            first_frame=_env_image("SEEDANCE_FIRST_FRAME"),
            last_frame=_env_image("SEEDANCE_LAST_FRAME"),
        ))

    @_seedance_live_mode(VideoGenerationMode.REFERENCE_TO_VIDEO)
    def test_reference_to_video(self) -> None:
        self._run_and_verify(self._request(
            VideoGenerationMode.REFERENCE_TO_VIDEO,
            reference_images=_reference_images(),
        ))


# ── MiniMax Hailuo API contract (offline) ────────────────────────────────────


def _video_request(
    mode: VideoGenerationMode,
    *,
    duration: float = 6,
) -> VideoGenerationInput:
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


class FakeMiniMaxClient:
    """MiniMax transport boundary; records submit/query/retrieve calls."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.downloads: list[str] = []
        self.closed = False

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/v1/video_generation":
            return {
                "task_id": "mm_task_1",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        if path == "/v1/query/video_generation":
            return {
                "task_id": "mm_task_1",
                "status": "Success",
                "file_id": "mm_file_1",
                "video_width": 1366,
                "video_height": 768,
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        if path == "/v1/files/retrieve":
            return {
                "file": {
                    "file_id": "mm_file_1",
                    "bytes": len(MP4),
                    "download_url": "https://cdn.example/video.mp4",
                },
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        raise AssertionError(f"unscripted MiniMax request: {method} {path}")

    def download(self, url, **kwargs):
        self.downloads.append(url)
        return MP4

    def close(self):
        self.closed = True


def _fake_minimax(**kwargs) -> MiniMaxH3Model:
    model = MiniMaxH3Model(api_key="test-key", poll_interval=0, **kwargs)
    model._client = FakeMiniMaxClient()
    return model


class TestMiniMaxAPI(unittest.TestCase):
    """Offline R9 checks for the API route of the hybrid MiniMax backend."""

    def test_signature_matches_seedance(self):
        for method in ("infer", "infer_and_save"):
            self.assertEqual(
                str(inspect.signature(getattr(MiniMaxH3Model, method))),
                str(inspect.signature(getattr(SeedanceModel, method))),
            )

    def test_construction_needs_no_credentials_and_cpu_is_accepted(self):
        saved = os.environ.pop("MINIMAX_API_KEY", None)
        try:
            self.assertEqual(MiniMaxH3Model(device="cpu").device, "cpu")
        finally:
            if saved is not None:
                os.environ["MINIMAX_API_KEY"] = saved

    def test_missing_key_is_actionable(self):
        saved = os.environ.pop("MINIMAX_API_KEY", None)
        try:
            with self.assertRaises(cloud_api.CloudAPIAuthError) as ctx:
                MiniMaxH3Model().infer(
                    _video_request(VideoGenerationMode.TEXT_TO_VIDEO)
                )
            self.assertIn("MINIMAX_API_KEY", str(ctx.exception))
            self.assertIn("http", str(ctx.exception))
        finally:
            if saved is not None:
                os.environ["MINIMAX_API_KEY"] = saved

    def test_submit_poll_retrieve_download(self):
        model = _fake_minimax()
        data = model.infer(_video_request(VideoGenerationMode.TEXT_TO_VIDEO))
        self.assertEqual(data, MP4)
        payload = model._client.calls[0][2]["json_body"]
        self.assertEqual(payload["model"], "MiniMax-Hailuo-2.3")
        self.assertNotIn("first_frame_image", payload)
        self.assertNotIn("seed", payload)
        self.assertEqual(model.last_call_info["task_id"], "mm_task_1")
        self.assertEqual(model.last_call_info["file_id"], "mm_file_1")

    def test_image_to_video_uses_png_data_uri(self):
        model = _fake_minimax()
        model.infer(_video_request(VideoGenerationMode.FIRST_FRAME_TO_VIDEO))
        payload = model._client.calls[0][2]["json_body"]
        self.assertTrue(payload["first_frame_image"].startswith("data:image/png;base64,"))

    def test_api_capabilities_are_model_specific(self):
        model = _fake_minimax()
        for mode in (
            VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO,
            VideoGenerationMode.REFERENCE_TO_VIDEO,
        ):
            with self.subTest(mode=mode), self.assertRaises(NotImplementedError):
                model.infer(_video_request(mode))

    def test_duration_and_resolution_matrix(self):
        with self.assertRaises(ValueError):
            _fake_minimax().infer(
                _video_request(VideoGenerationMode.TEXT_TO_VIDEO, duration=5)
            )
        with self.assertRaises(ValueError):
            _fake_minimax(resolution="1080P").infer(
                _video_request(VideoGenerationMode.TEXT_TO_VIDEO, duration=10)
            )

    def test_cache_hit_sends_no_network_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = _video_request(VideoGenerationMode.TEXT_TO_VIDEO)
            self.assertEqual(_fake_minimax(cache_dir=tmp).infer(request), MP4)
            second = _fake_minimax(cache_dir=tmp)
            self.assertEqual(second.infer(request), MP4)
            self.assertEqual(second._client.calls, [])
            self.assertTrue(second.last_call_info["cached"])

    def test_infer_and_save_writes_caller_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "video.mp4"
            returned = _fake_minimax().infer_and_save(
                _video_request(VideoGenerationMode.TEXT_TO_VIDEO), str(out)
            )
            self.assertEqual(returned, str(out))
            self.assertEqual(out.read_bytes(), MP4)

    def test_unload_is_idempotent(self):
        model = _fake_minimax()
        client = model._client
        model.unload()
        model.unload()
        self.assertTrue(client.closed)
        self.assertIsNone(model._client)


# ── MiniMax paid live checks ─────────────────────────────────────────────────


_RUN_MINIMAX_LIVE = os.environ.get("AAAGF_RUN_MINIMAX_LIVE") == "1"
_MINIMAX_MODES = {
    item.strip()
    for item in os.environ.get("MINIMAX_LIVE_MODES", "text_to_video").split(",")
    if item.strip()
}


def _minimax_live_mode(mode: VideoGenerationMode):
    enabled = _RUN_MINIMAX_LIVE and mode.value in _MINIMAX_MODES
    return unittest.skipUnless(
        enabled,
        "paid MiniMax check disabled; set AAAGF_RUN_MINIMAX_LIVE=1 and "
        f"include {mode.value!r} in MINIMAX_LIVE_MODES",
    )


class TestMiniMaxLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not _RUN_MINIMAX_LIVE:
            raise unittest.SkipTest(
                "paid MiniMax checks require AAAGF_RUN_MINIMAX_LIVE=1"
            )
        if not os.environ.get("MINIMAX_API_KEY"):
            raise RuntimeError("MINIMAX_API_KEY is required for the paid live check")
        cls.output_dir = Path(
            os.environ.get(
                "MINIMAX_OUTPUT_DIR",
                str(Path(tempfile.gettempdir()) / "aaagf_minimax_h3_live"),
            )
        ).expanduser()
        cls.output_dir.mkdir(parents=True, exist_ok=True)
        cls.model = MiniMaxH3Model(
            model_path=os.environ.get("MINIMAX_VIDEO_MODEL", "MiniMax-Hailuo-2.3"),
            cache_dir=str(cls.output_dir / "cache"),
            resolution=os.environ.get("MINIMAX_RESOLUTION", "768P"),
            timeout=int(os.environ.get("MINIMAX_TASK_TIMEOUT", "1800")),
            poll_interval=float(os.environ.get("MINIMAX_POLL_INTERVAL", "10")),
            verbose=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        model = getattr(cls, "model", None)
        if model is not None:
            model.unload()

    def _run(self, mode: VideoGenerationMode, **images) -> None:
        request = VideoGenerationInput(
            mode=mode,
            prompt=os.environ.get(
                "MINIMAX_PROMPT",
                "A small paper dragon flies above misty mountains, cinematic light.",
            ),
            duration_sec=int(os.environ.get("MINIMAX_DURATION_SEC", "6")),
            seed=42,
            **images,
        )
        out = self.output_dir / f"minimax_{mode.value}.mp4"
        returned = self.model.infer_and_save(request, str(out))
        self.assertEqual(returned, str(out))
        self.assertGreater(out.stat().st_size, 0)
        self.assertIn(b"ftyp", out.read_bytes()[:64])

    @_minimax_live_mode(VideoGenerationMode.TEXT_TO_VIDEO)
    def test_text_to_video(self) -> None:
        self._run(VideoGenerationMode.TEXT_TO_VIDEO)

    @_minimax_live_mode(VideoGenerationMode.FIRST_FRAME_TO_VIDEO)
    def test_image_to_video(self) -> None:
        self._run(
            VideoGenerationMode.FIRST_FRAME_TO_VIDEO,
            first_frame=_env_image("MINIMAX_FIRST_FRAME"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
