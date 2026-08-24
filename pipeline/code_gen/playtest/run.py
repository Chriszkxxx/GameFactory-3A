"""Record one generated game playtest.

The engine switch lives here so a second engine can be added without leaking
its recording implementation into the three.js adapter. Everything about *how*
a browser is driven belongs to `engine_adapters/<engine>/playtest/`.

Recording on a headless box needs three things the game itself does not carry:
a Playwright install, a browser, and the shared libraries Chromium is missing
from this image. `--recorder-root` supplies all three from one conventional
layout, so the usual invocation names a project and a URL and nothing else.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine_adapters.three_js import ThreeClient

SUPPORTED_ENGINES = ("three_js",)

#: Layout of a recorder root: a Node project with Playwright installed, the
#: browsers it downloaded, and a conda prefix holding Chromium's missing
#: libraries. Kept as data because the same three paths are needed by any engine
#: that drives a browser.
_RECORDER_LAYOUT = {
    "playwright_root": ".",
    "browsers_path": "browsers",
    "library_path": "deps/lib",
}


def default_output_dir(project: Path) -> Path:
    """Put a take beside the game, stamped, so takes accumulate rather than overwrite."""
    return project / ".a3game" / "playtest" / datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_recorder_root(root: str | Path | None) -> dict[str, Path]:
    """Expand a recorder root into the paths the adapter needs."""
    if not root:
        return {}
    base = Path(root).expanduser().resolve(strict=False)
    return {
        key: (base if value == "." else base / value)
        for key, value in _RECORDER_LAYOUT.items()
    }


def record_playtest(
    *,
    engine: str = "three_js",
    project: str | Path,
    output_dir: str | Path | None = None,
    url: str = "",
    action_plan: str | Path | None = None,
    recorder_root: str | Path | None = None,
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
    """Dispatch one recording to the engine adapter that owns the browser."""
    name = str(engine).strip().lower()
    if name not in SUPPORTED_ENGINES:
        return {
            "ok": False,
            "operation": "playtest.record",
            "engine": name,
            "errors": [f"Unsupported engine {engine!r}; supported: {', '.join(SUPPORTED_ENGINES)}"],
        }

    # Explicit arguments win over the recorder root, so one part of a layout can
    # be overridden without abandoning the rest of it.
    derived = resolve_recorder_root(recorder_root)
    project_path = Path(project).expanduser().resolve(strict=False)
    result = ThreeClient(project_path=project_path).playtest.record(
        output_dir=output_dir or default_output_dir(project_path),
        url=url,
        action_plan=action_plan,
        playwright_root=playwright_root or derived.get("playwright_root"),
        browser_executable=browser_executable,
        browsers_path=browsers_path or derived.get("browsers_path"),
        library_path=library_path or derived.get("library_path"),
        ffmpeg=ffmpeg,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        timeout=timeout,
        dry_run=dry_run,
    )
    result["engine"] = name
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover and record a generated game playtest.")
    parser.add_argument("--engine", choices=SUPPORTED_ENGINES, default="three_js")
    parser.add_argument("--project", required=True, help="Game project directory or its package.json")
    parser.add_argument("--url", default="", help="Running dev server; defaults to the adapter's dev-server URL")
    parser.add_argument("--out-dir", default="", help="Defaults to <project>/.a3game/playtest/<timestamp>")
    parser.add_argument("--action-plan", default="", help="JSON array or {actions:[...]}; overrides discovery")
    parser.add_argument("--recorder-root", default="", help="Supplies playwright/, browsers/ and deps/lib in one flag")
    parser.add_argument("--playwright-root", default="", help="Project containing node_modules/playwright")
    parser.add_argument("--browser-executable", default="", help="Chromium binary to use")
    parser.add_argument("--browsers-path", default="", help="PLAYWRIGHT_BROWSERS_PATH for the recorder")
    parser.add_argument("--library-path", default="", help="Prepended to LD_LIBRARY_PATH for Chromium's missing libraries")
    parser.add_argument("--ffmpeg", default="", help="ffmpeg binary used to encode the take")
    parser.add_argument("--duration", type=float, default=12.0, help="Seconds of video to record")
    parser.add_argument("--fps", type=int, default=20, help="Simulation and video frame rate")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--timeout", type=float, default=900.0, help="SwiftShader is slow; a 12s take can take minutes")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = record_playtest(
        engine=args.engine,
        project=args.project,
        output_dir=args.out_dir or None,
        url=args.url,
        action_plan=args.action_plan or None,
        recorder_root=args.recorder_root or None,
        playwright_root=args.playwright_root or None,
        browser_executable=args.browser_executable or None,
        browsers_path=args.browsers_path or None,
        library_path=args.library_path or None,
        ffmpeg=args.ffmpeg or None,
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
