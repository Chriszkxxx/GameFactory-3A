"""Record a playtest of a blender project from host Python.

This is a **fixed-timestep capture**, not screen recording. ``record.py`` is
the blender counterpart of ``three_js/playtest/record.mjs``: it has to be
Python because it runs inside a ``bpy`` interpreter, not Node. It drives the
game through the same ``Controls`` surface a keyboard would, then writes
``frames/``, ``video.mp4`` and ``report.json``.

One environment input has no default on a machine like this and is therefore
an explicit parameter rather than an assumption:

- ``blender`` / ``blender_root`` - a Blender application, or a Python that
  can ``import bpy``. ``A3GAME_BLENDER_ROOT`` / ``AAAGF_BLENDER`` / ``BLENDER``
  are read when this is omitted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .._internal.transport import BlenderToolchain
from ..config import BlenderClientConfig
from ..contracts import BlenderOperationResult

_RECORDER = Path(__file__).with_name("record.py")
_OPERATION = "playtest.record"
_REPO_ROOT = Path(__file__).resolve().parents[3]


class BlenderPlaytestClient:
    """Drive a running game through discovered actions and record the result.

    Actions are discovered from the game rather than configured, so this works
    on a project it has never seen. In order of preference: a declared
    ``playtest_actions`` plan; the input tables ``from_held`` dispatches on;
    a generic keyboard plan.
    """

    def __init__(self, config: BlenderClientConfig) -> None:
        self._config = config
        self._toolchain = BlenderToolchain(config)

    def record(
        self,
        *,
        output_dir: str | Path,
        action_plan: str | Path | None = None,
        blender: str | Path | None = None,
        ffmpeg: str | Path | None = None,
        spec: str | Path | None = None,
        duration: float = 12.0,
        fps: int = 20,
        width: int = 640,
        height: int = 360,
        samples: int = 8,
        device: str = "CPU",
        timeout: float = 900.0,
        dry_run: bool = False,
        no_render: bool = False,
    ) -> dict[str, Any]:
        """Record one playtest into ``output_dir``.

        Writes ``frames/f%05d.jpg``, ``video.mp4`` and ``report.json``. The
        report is the evidence: it names every action that was found and run,
        and carries the game's own ``summary()`` so a reviewer can see that the
        game responded rather than merely rendered.

        ``timeout`` is generous by default because Cycles is the cost here.
        ``no_render`` is the cheap test take: simulate and bake, skip the clip.
        """
        project_dir = self._config.project_dir
        project_file = self._config.project_file
        if project_dir is None or project_file is None or not project_file.is_file():
            return self._fail(
                "project_path must resolve to a project containing game.py"
            )
        if not _RECORDER.is_file():
            return self._fail(f"Playtest recorder is missing: {_RECORDER}")
        if duration <= 0 or fps <= 0 or width <= 0 or height <= 0:
            return self._fail("duration, fps, width, and height must be positive")

        out = Path(output_dir).expanduser().resolve(strict=False)
        plan = self._resolve(action_plan)
        spec_path = self._resolve(spec)
        binary = self._resolve(blender) or self._config.blender_executable
        encoder = self._resolve(ffmpeg)

        if plan is not None and not plan.is_file():
            return self._fail(f"action_plan does not exist: {plan}")
        if spec_path is not None and not spec_path.is_file():
            return self._fail(f"spec does not exist: {spec_path}")
        if binary is not None and not binary.is_file():
            return self._fail(f"blender executable does not exist: {binary}")

        report_path = out / "report.json"
        arguments = [
            "--game", str(project_file),
            "--output-dir", str(out),
            "--duration", str(float(duration)),
            "--fps", str(int(fps)),
            "--width", str(int(width)),
            "--height", str(int(height)),
            "--samples", str(int(samples)),
            "--device", str(device),
        ]
        for flag, value in (
            ("--action-plan", plan),
            ("--spec", spec_path),
            ("--ffmpeg", encoder),
        ):
            if value is not None:
                arguments.extend([flag, str(value)])
        if no_render:
            arguments.append("--no-render")

        environment: dict[str, str] = {
            "AAAGF_BLENDER_EXIT_ON_DONE": "1",
            "GAMEFACTORY3A_ROOT": str(_REPO_ROOT),
        }
        if encoder is not None:
            environment["A3GAME_PLAYTEST_FFMPEG"] = str(encoder)

        payload: dict[str, Any] = {
            "engine": "blender",
            "game": str(project_file),
            "project_dir": str(project_dir),
            "output_dir": str(out),
            "report_path": str(report_path),
            "action_plan": str(plan) if plan else None,
            "blender": str(binary) if binary else None,
            "ffmpeg": str(encoder) if encoder else None,
            "duration": duration,
            "fps": fps,
            "viewport": {"width": width, "height": height},
            "samples": samples,
            "device": device,
            "no_render": no_render,
            "environment": environment,
            "dry_run": dry_run,
        }
        if dry_run:
            return BlenderOperationResult.success(_OPERATION, payload=payload).to_dict()

        out.mkdir(parents=True, exist_ok=True)
        try:
            command = self._toolchain.run_script(
                _RECORDER,
                cwd=project_dir,
                extra_args=arguments,
                timeout=timeout,
                environment=environment,
                blender=binary,
            )
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            return self._fail(f"{type(exc).__name__}: {exc}", payload)
        payload["command"] = command.to_dict()

        report: dict[str, Any] | None = None
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return self._fail(f"Invalid playtest report: {exc}", payload)
        payload["report"] = report

        if report is None:
            reason = (
                "Recorder timed out before writing a report"
                if command.timed_out
                else "Recorder produced no report.json"
            )
            return self._fail(reason, payload)
        # A partial take is a real result: the recorder keeps what it captured
        # when a renderer dies, and that is more useful than discarding it.
        if not report.get("frames"):
            return self._fail(
                report.get("error") or report.get("crash") or "Recorder captured no frames",
                payload,
            )

        artifacts = [
            {"type": "playtest_report", "path": str(report_path)},
        ]
        frames_dir = out / "frames"
        if frames_dir.is_dir() and any(frames_dir.iterdir()):
            artifacts.append({"type": "playtest_frames", "path": str(frames_dir)})
        if report.get("video"):
            artifacts.append({"type": "playtest_video", "path": str(report["video"])})
        return BlenderOperationResult.success(
            _OPERATION,
            artifacts=artifacts,
            warnings=[str(item) for item in report.get("warnings", [])],
            payload=payload,
        ).to_dict()

    @staticmethod
    def _resolve(value: str | Path | None) -> Path | None:
        return Path(value).expanduser().resolve(strict=False) if value else None

    @staticmethod
    def _fail(message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return BlenderOperationResult.failure(
            _OPERATION, message, payload=payload
        ).to_dict()
