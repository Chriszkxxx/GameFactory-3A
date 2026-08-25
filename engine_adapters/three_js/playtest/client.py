"""Record a playtest of a three.js project in a headless browser.

This is a **fixed-timestep capture**, not screen recording: there is no display
and no GPU render node here, so WebGL runs on SwiftShader at a fraction of real
time. `record.mjs` documents why each part is shaped the way it is.

Three environment inputs have no default on a machine like this and are
therefore explicit parameters rather than assumptions:

- ``playwright_root`` - a project with ``node_modules/playwright``. A generated
  game does not depend on Playwright, and it should not have to: recording is
  the harness's concern, not the game's.
- ``browser_executable`` / ``browsers_path`` - the browser is not in the default
  ``~/.cache`` location.
- ``library_path`` - Chromium needs ``libatk-bridge-2.0``, ``libgbm`` and
  ``libatspi``, which are absent from this image and cannot be installed. They
  are supplied by prepending a directory to ``LD_LIBRARY_PATH``. Omitting this is
  the single most likely reason a recording fails to start, and the failure looks
  like a browser launch error rather than a missing library.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .._internal.transport import NodeToolchain
from ..config import ThreeClientConfig
from ..contracts import ThreeOperationResult

_RECORDER = Path(__file__).with_name("record.mjs")
_OPERATION = "playtest.record"


class ThreePlaytestClient:
    """Drive a running game through discovered actions and record the result.

    Nothing here is written for a particular game. What the recorder needs to
    know is read from the running game — the input router publishes the very
    tables it dispatches on, so they cannot drift from what the game listens
    for. In order of preference: a ``__A3GAME_PLAYTEST__`` plan the game
    declares for itself; ``actionBindings`` and ``keyBindings``;
    ``[data-game-action]`` elements; a generic keyboard plan.

    Three things vary per game that a *list of verbs* cannot express, so they
    are separate inputs — inferred by default, overridable per recording:

    - ``hold`` - what stays pressed for the whole take. A racing game whose
      throttle is released between actions records a car twitching on the
      start line.
    - ``warmup`` - seconds to simulate before capturing. Games open on a
      countdown or a spawn, and a brawler drops attacks entirely until its
      round reaches FIGHT.
    - ``look`` - whether sweeping the camera is meaningful. Wrong in a
      side-scroller, actively harmful under drag-look.
    """

    def __init__(self, config: ThreeClientConfig) -> None:
        self._config = config
        self._toolchain = NodeToolchain(config)

    def record(
        self,
        *,
        output_dir: str | Path,
        url: str = "",
        action_plan: str | Path | None = None,
        hold: str | list[str] | None = None,
        warmup: float = 0.0,
        look: str = "auto",
        playwright_root: str | Path | None = None,
        browser_executable: str | Path | None = None,
        browsers_path: str | Path | None = None,
        library_path: str | Path | None = None,
        ffmpeg: str | Path | None = None,
        duration: float = 12.0,
        fps: int = 20,
        width: int = 640,
        height: int = 360,
        timeout: float = 900.0,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Record one playtest into ``output_dir``.

        Writes ``frames/f%05d.jpg``, ``video.mp4`` and ``report.json``. The
        report is the evidence: it names every action that was found and run,
        and carries the game's own ``getState()`` so a reviewer can see that the
        game responded rather than merely rendered.

        Args:
            action_plan: JSON overriding discovery entirely. Either a bare array
                of actions or ``{warmup?, hold?, look?, actions:[...]}``, where
                an action is ``{id, keys?, taps?, mouse?, hold?, click?,
                duration?}``. ``keys`` are held for the action's slot, ``taps``
                are pressed for one frame, and ``hold`` turns a tap into
                charge-and-release (draw a bow, hold a guard).
            hold: Actions or key codes pressed for the entire take. Names are
                resolved through the game's own bindings, so ``["accelerate"]``
                works without knowing which key that is.
            warmup: Seconds simulated but not captured, for opening ceremony.
            look: ``auto`` (sweep unless the game uses drag-look), ``pan``, or
                ``off``. A sweep starts from the game's own opening framing
                rather than from zero.
            timeout: Generous by default because SwiftShader is the cost here:
                ~0.6 s/frame for a first-person arena and up to 6 s/frame for a
                scene with a long view. A 12 s take at 20 fps is 240 frames.
        """
        project_dir = self._config.project_dir
        project_file = self._config.project_file
        if project_dir is None or project_file is None or not project_file.is_file():
            return self._fail("project_path must resolve to a project containing package.json")
        if not _RECORDER.is_file():
            return self._fail(f"Playtest recorder is missing: {_RECORDER}")
        if duration <= 0 or fps <= 0 or width <= 0 or height <= 0:
            return self._fail("duration, fps, width, and height must be positive")

        out = Path(output_dir).expanduser().resolve(strict=False)
        plan = self._resolve(action_plan)
        root = self._resolve(playwright_root)
        browser = self._resolve(browser_executable)
        browsers = self._resolve(browsers_path)
        libraries = self._resolve(library_path)
        encoder = self._resolve(ffmpeg)

        if plan is not None and not plan.is_file():
            return self._fail(f"action_plan does not exist: {plan}")
        if root is not None and not (root / "node_modules" / "playwright").is_dir():
            return self._fail(f"playwright_root has no node_modules/playwright: {root}")
        if browser is not None and not browser.is_file():
            return self._fail(f"browser_executable does not exist: {browser}")
        if libraries is not None and not libraries.is_dir():
            return self._fail(f"library_path is not a directory: {libraries}")
        if look not in ("auto", "pan", "off"):
            return self._fail(f"look must be auto, pan, or off; got {look!r}")
        if warmup < 0:
            return self._fail("warmup cannot be negative")

        held = [item.strip() for item in (hold.split(",") if isinstance(hold, str) else hold or [])]
        held = [item for item in held if item]
        url = str(url or self._config.dev_server_url).rstrip("/")
        report_path = out / "report.json"
        arguments = [
            "--url", url,
            "--output-dir", str(out),
            "--duration", str(float(duration)),
            "--fps", str(int(fps)),
            "--width", str(int(width)),
            "--height", str(int(height)),
            "--look", look,
        ]
        if warmup > 0:
            arguments.extend(["--warmup", str(float(warmup))])
        if held:
            arguments.extend(["--hold", ",".join(held)])
        for flag, value in (
            ("--action-plan", plan),
            ("--playwright-root", root),
            ("--browser-executable", browser),
        ):
            if value is not None:
                arguments.extend([flag, str(value)])

        environment: dict[str, str] = {}
        if browsers is not None:
            environment["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
        if libraries is not None:
            # Prepend: the image's own libraries must still win where they exist.
            existing = self._toolchain_environment().get("LD_LIBRARY_PATH", "")
            environment["LD_LIBRARY_PATH"] = (
                f"{libraries}:{existing}" if existing else str(libraries)
            )
        if encoder is not None:
            environment["A3GAME_PLAYTEST_FFMPEG"] = str(encoder)

        payload: dict[str, Any] = {
            "engine": "three_js",
            "url": url,
            "project_dir": str(project_dir),
            "output_dir": str(out),
            "report_path": str(report_path),
            "action_plan": str(plan) if plan else None,
            "hold": held,
            "warmup": warmup,
            "look": look,
            "playwright_root": str(root) if root else None,
            "browser_executable": str(browser) if browser else None,
            "duration": duration,
            "fps": fps,
            "viewport": {"width": width, "height": height},
            "environment": environment,
            "dry_run": dry_run,
        }
        if dry_run:
            return ThreeOperationResult.success(_OPERATION, payload=payload).to_dict()

        out.mkdir(parents=True, exist_ok=True)
        try:
            command = self._toolchain.run_node(
                _RECORDER,
                cwd=project_dir,
                extra_args=arguments,
                timeout=timeout,
                environment=environment or None,
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
            {"type": "playtest_frames", "path": str(out / "frames")},
        ]
        if report.get("video"):
            artifacts.append({"type": "playtest_video", "path": str(report["video"])})
        return ThreeOperationResult.success(
            _OPERATION,
            artifacts=artifacts,
            warnings=[str(item) for item in report.get("warnings", [])],
            payload=payload,
        ).to_dict()

    @staticmethod
    def _resolve(value: str | Path | None) -> Path | None:
        return Path(value).expanduser().resolve(strict=False) if value else None

    @staticmethod
    def _toolchain_environment() -> dict[str, str]:
        import os

        return dict(os.environ)

    @staticmethod
    def _fail(message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return ThreeOperationResult.failure(_OPERATION, message, payload=payload).to_dict()
