"""Lightweight, model-free quality checks for generated WAV assets."""
from __future__ import annotations

import wave
from pathlib import Path
from typing import Any


def evaluate(result: dict, task: dict) -> dict[str, Any]:
    """Measure validity, duration, level, silence, and clipping from an existing WAV."""
    import numpy as np

    audio_path = Path(result.get("audio_path") or "")
    if not audio_path.is_file():
        return {"valid_audio": 0.0, "error": f"Missing audio artifact: {audio_path}"}
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frames_count = wav_file.getnframes()
            frames = wav_file.readframes(frames_count)
        if sample_width != 2:
            return {
                "valid_audio": 0.0,
                "error": f"Expected PCM16 WAV, got {sample_width * 8}-bit samples",
            }
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            audio = audio.reshape(-1, channels)
        duration = frames_count / sample_rate if sample_rate else 0.0
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        requested = task.get("duration_sec")
        if requested:
            duration_match = max(0.0, 1.0 - abs(duration - float(requested)) / float(requested))
        else:
            duration_match = 1.0
        target_rate = task.get("sample_rate")
        return {
            "valid_audio": 1.0 if audio.size and sample_rate > 0 else 0.0,
            "duration_sec": round(float(duration), 4),
            "duration_match": round(float(duration_match), 4),
            "sample_rate_match": 1.0 if not target_rate or int(target_rate) == sample_rate else 0.0,
            "peak": round(peak, 6),
            "rms": round(rms, 6),
            "rms_dbfs": round(float(20.0 * np.log10(max(rms, 1e-8))), 4),
            "non_silence": 1.0 if rms >= 1e-4 else 0.0,
            "clipping_fraction": round(float(np.mean(np.abs(audio) >= 0.999)), 6),
        }
    except (OSError, EOFError, ValueError, wave.Error) as exc:
        return {"valid_audio": 0.0, "error": str(exc)}
