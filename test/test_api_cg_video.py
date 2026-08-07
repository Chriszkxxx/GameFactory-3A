"""Live Seedance integration checks.

Unlike the other API contract tests, this module talks to the real Volcengine
Ark service.  Normal test discovery skips every check so CI and local unit-test
runs cannot spend credits accidentally.  Opt in explicitly:

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
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from models.gen_cg_video import (  # noqa: E402
    SeedanceModel,
    VideoGenerationInput,
    VideoGenerationMode,
)


_RUN_LIVE = os.environ.get("AAAGF_RUN_SEEDANCE_LIVE") == "1"
_DEFAULT_MODE = VideoGenerationMode.TEXT_TO_VIDEO.value
_SELECTED_MODES = {
    value.strip()
    for value in os.environ.get("SEEDANCE_LIVE_MODES", _DEFAULT_MODE).split(",")
    if value.strip()
}


def _live_mode(mode: VideoGenerationMode):
    """Skip a paid test unless both global opt-in and mode opt-in are present."""

    enabled = _RUN_LIVE and mode.value in _SELECTED_MODES
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
        if not _RUN_LIVE:
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

    @_live_mode(VideoGenerationMode.TEXT_TO_VIDEO)
    def test_text_to_video(self) -> None:
        self._run_and_verify(self._request(VideoGenerationMode.TEXT_TO_VIDEO))

    @_live_mode(VideoGenerationMode.FIRST_FRAME_TO_VIDEO)
    def test_first_frame_to_video(self) -> None:
        self._run_and_verify(self._request(
            VideoGenerationMode.FIRST_FRAME_TO_VIDEO,
            first_frame=_env_image("SEEDANCE_FIRST_FRAME"),
        ))

    @_live_mode(VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO)
    def test_first_last_frame_to_video(self) -> None:
        self._run_and_verify(self._request(
            VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO,
            first_frame=_env_image("SEEDANCE_FIRST_FRAME"),
            last_frame=_env_image("SEEDANCE_LAST_FRAME"),
        ))

    @_live_mode(VideoGenerationMode.REFERENCE_TO_VIDEO)
    def test_reference_to_video(self) -> None:
        self._run_and_verify(self._request(
            VideoGenerationMode.REFERENCE_TO_VIDEO,
            reference_images=_reference_images(),
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
