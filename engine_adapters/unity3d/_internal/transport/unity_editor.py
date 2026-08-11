"""Private Unity editor subprocess transport.

Unity does not have Unreal's Python Remote Execution or HTTP Remote Control.
This transport uses the ``-batchmode -quit -executeMethod`` CLI pattern:

1. Write args to a JSON job file
2. Run ``Unity -batchmode -quit -projectPath <proj> -executeMethod <Class.Method>``
3. The C# script writes a JSON report to a temp file
4. The Python transport reads the JSON report and returns it
"""

from __future__ import annotations

import glob
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ...config import UnityClientConfig


def find_unity_binary(
    explicit: str | Path | None = None,
) -> Path | None:
    """Locate a Unity editor binary; newest installed version wins."""
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_dir():
            candidates = _unity_binary_candidates(path)
            existing = next(
                (candidate for candidate in candidates if candidate.is_file()),
                None,
            )
            return existing or path
        return path
    env_value = (
        os.environ.get("A3GAME_UNITY_ROOT")
        or os.environ.get("AAAGF_UNITY")
    )
    if env_value:
        return Path(env_value)

    patterns = {
        "Windows": [
            r"C:\Program Files\Unity\Hub\Editor\*\Editor\Unity.exe",
        ],
        "Darwin": [
            "/Applications/Unity/Hub/Editor/*/Unity.app/Contents/MacOS/Unity",
        ],
        "Linux": [
            str(Path.home() / "Unity" / "Hub" / "Editor" / "*" / "Editor" / "Unity"),
        ],
    }.get(platform.system(), [])
    found = sorted(
        p for pattern in patterns for p in glob.glob(pattern)
    )
    return Path(found[-1]) if found else None


def _unity_binary_candidates(root: Path) -> list[Path]:
    """Return platform layouts accepted for an explicit Unity install root."""
    return [
        root / "Unity.app" / "Contents" / "MacOS" / "Unity",
        root / "Contents" / "MacOS" / "Unity",
        root / "Editor" / "Unity.exe",
        root / "Unity.exe",
        root / "Editor" / "Unity",
        root / "Unity",
    ]


def install_editor_script(
    project_path: Path | None,
    class_method: str,
) -> Path | None:
    """Install a bundled Editor script required by an executeMethod call."""
    if project_path is None or not project_path.is_dir():
        return None
    class_name = str(class_method or "").split(".", 1)[0].strip()
    if not class_name:
        return None
    source = (
        Path(__file__).resolve().parents[2]
        / "import_generated"
        / f"{class_name}.cs"
    )
    if not source.is_file():
        return None
    destination = project_path / "Assets" / "Editor" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = source.read_bytes()
    if not destination.is_file() or destination.read_bytes() != source_bytes:
        destination.write_bytes(source_bytes)
    return destination


class UnityEditorTransport:
    """Subprocess-based transport for Unity editor batchmode operations."""

    def __init__(
        self,
        config: UnityClientConfig | None = None,
    ) -> None:
        self.config = config or UnityClientConfig.resolve()
        self._processes: dict[int, subprocess.Popen[Any]] = {}

    @property
    def unity_binary(self) -> Path | None:
        return find_unity_binary(self.config.unity_root)

    def execute_method(
        self,
        class_method: str,
        *,
        args: dict[str, Any] | None = None,
        timeout: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run a Unity ``-executeMethod`` invocation and return the JSON report."""
        unity = self.unity_binary
        project_path = self.config.project_path

        resolved_timeout = timeout or self.config.editor_batchmode_timeout
        report_path = Path(
            tempfile.mktemp(
                suffix=".json",
                prefix="unity_report_",
            )
        )
        job_args = dict(args or {})
        job_path = Path(
            tempfile.mktemp(
                suffix=".json",
                prefix="unity_job_",
            )
        )
        job_path.parent.mkdir(parents=True, exist_ok=True)
        job_path.write_text(
            json.dumps(job_args, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log_path = report_path.with_suffix(".unity.log")

        command = [
            str(unity) if unity else "Unity",
            "-batchmode",
            "-quit",
            "-nographics",
            "-projectPath",
            str(project_path) if project_path else "",
            "-executeMethod",
            str(class_method),
            "-logFile",
            str(log_path),
            "--job",
            str(job_path),
            "--report",
            str(report_path),
        ]

        payload: dict[str, Any] = {
            "command": command,
            "class_method": class_method,
            "project_path": str(project_path) if project_path else "",
            "job_path": str(job_path),
            "report_path": str(report_path),
            "log_path": str(log_path),
            "dry_run": dry_run,
            "timeout": resolved_timeout,
        }
        if dry_run:
            return {"ok": True, "dry_run": True, **payload}

        if unity is None or not unity.exists():
            return {
                "ok": False,
                "error": (
                    f"Unity editor binary was not found: {unity or '<not configured>'}"
                ),
            }
        if project_path is None or not project_path.is_dir():
            return {
                "ok": False,
                "error": (
                    f"Unity project path is not a directory: {project_path}"
                ),
            }

        try:
            installed_script = install_editor_script(
                project_path,
                class_method,
            )
        except OSError as exc:
            return {
                "ok": False,
                "error": (
                    "Unity Editor script could not be installed for "
                    f"{class_method}: {type(exc).__name__}: {exc}"
                ),
                **payload,
            }
        if installed_script is not None:
            payload["editor_script"] = str(installed_script)

        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=resolved_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            payload["returncode"] = None
            payload["timed_out"] = True
            payload["stdout"] = str(exc.stdout or "")
            payload["stderr"] = str(exc.stderr or "")
            return {
                "ok": False,
                "error": (
                    f"Unity batchmode timed out after {resolved_timeout}s"
                ),
                **payload,
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                **payload,
            }

        payload["returncode"] = completed.returncode
        process_log = (
            log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if log_path.is_file()
            else ""
        )
        payload["stdout"] = process_log
        payload["stderr"] = ""

        if report_path.is_file():
            try:
                report = json.loads(
                    report_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "error": (
                        f"Unity report JSON could not be parsed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    **payload,
                }
            if isinstance(report, dict):
                report.setdefault("returncode", completed.returncode)
                report.setdefault("stdout", process_log)
                report.setdefault("stderr", "")
                report.setdefault("class_method", class_method)
                report.setdefault("project_path", str(project_path))
                report.setdefault("job_path", str(job_path))
                report.setdefault("report_path", str(report_path))
                report.setdefault("log_path", str(log_path))
                if completed.returncode != 0 and report.get("ok", True):
                    report["ok"] = False
                    report.setdefault("errors", [])
                    report["errors"] = list(report["errors"]) + [
                        f"Unity exited with code {completed.returncode}"
                    ]
                return report
            return {
                "ok": False,
                "error": "Unity report root must be a JSON object",
                **payload,
            }
        return {
            "ok": False,
            "error": (
                f"Unity wrote no report file (exit {completed.returncode}); "
                f"see log: {log_path}"
            ),
            **payload,
        }

    def execute_json(
        self,
        class_method: str,
        *,
        args: dict[str, Any] | None = None,
        timeout: int = 120,
    ) -> Any:
        """Run an editor method and return the report JSON directly."""
        result = self.execute_method(
            class_method,
            args=args,
            timeout=timeout,
        )
        return result

    def is_ready(self, timeout: float = 5.0) -> bool:
        """Check if Unity editor is running and responsive."""
        unity = self.unity_binary
        if unity is None or not unity.exists():
            return False
        project_path = self.config.project_path
        if project_path is None or not project_path.is_dir():
            return False
        try:
            result = self.execute_method(
                "StatusCheck.RunFromCLI",
                timeout=int(timeout),
            )
            return bool(result.get("ok"))
        except Exception:
            return False

    def launch_editor(
        self,
        scene_path: str = "",
        extra_args: list[str] | None = None,
    ) -> subprocess.Popen[Any]:
        """Launch the Unity editor with GUI for runtime sessions."""
        unity = self.unity_binary
        project_path = self.config.project_path
        if unity is None or not unity.exists():
            raise FileNotFoundError(
                f"Unity editor binary was not found: {unity}"
            )
        if project_path is None or not project_path.is_dir():
            raise FileNotFoundError(
                f"Unity project path is not a directory: {project_path}"
            )
        command = [
            str(unity),
            "-projectPath",
            str(project_path),
        ]
        if scene_path:
            command.append(str(scene_path))
        command.append(
            f"-A3GameRuntimeInputPort={self.config.runtime_port}"
        )
        command.extend(extra_args or [])

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(
            command,
            cwd=str(project_path),
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        self._processes[process.pid] = process
        return process

    def stop_editor(self, process_id: int) -> bool:
        """Terminate a tracked Unity editor process."""
        process = self._processes.get(int(process_id))
        if process is None:
            return False
        if process.poll() is None:
            process.terminate()
        self._processes.pop(process.pid, None)
        return True
