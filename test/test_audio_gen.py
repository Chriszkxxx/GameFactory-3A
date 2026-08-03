"""CPU-only contract tests for both logical AudioGen routes."""
from __future__ import annotations

import sys
import tempfile
import unittest
import wave
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HARNESS = _REPO_ROOT / "test" / "harness"
for _path in (str(_REPO_ROOT), str(_HARNESS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import stubs  # noqa: E402


class AudioGenContractTest(unittest.TestCase):
    def _assert_wav(self, path: str, expected_rate: int) -> None:
        audio_path = Path(path)
        self.assertTrue(audio_path.is_file())
        with wave.open(str(audio_path), "rb") as wav_file:
            self.assertEqual(wav_file.getframerate(), expected_rate)
            self.assertGreater(wav_file.getnframes(), 0)

    def test_dialogue_and_sound_effect_routes(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            operator = stubs.build_operator("audio", output_dir=output_dir)
            dialogue = operator.run({
                "task_id": "dialogue_001",
                "audio_type": "dialogue",
                "text": "发现目标",
                "language": "Chinese",
                "speaker_id": "Vivian",
                "sample_rate": 24_000,
            })
            sound_effect = operator.run({
                "task_id": "rifle_001",
                "audio_type": "sound_effect",
                "sound_category": "one_shot",
                "prompt": "a single futuristic rifle shot",
                "duration_sec": 0.5,
                "sample_rate": 48_000,
            })
            self._assert_wav(dialogue["audio_path"], 24_000)
            self._assert_wav(sound_effect["audio_path"], 48_000)
            self.assertEqual(dialogue["audio_type"], "dialogue")
            self.assertEqual(sound_effect["audio_type"], "sound_effect")


if __name__ == "__main__":
    unittest.main()
