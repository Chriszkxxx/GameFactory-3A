"""Non-interactive Codex CLI backend for Mechanic generation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import (
    validate_agent_request,
    validate_agent_result,
)


_IGNORED_SNAPSHOT_PREFIXES = (
    "project/Binaries/",
    "project/Content/",
    "project/DerivedDataCache/",
    "project/Intermediate/",
    "project/Saved/",
    "project/Plugins/AAAGamePlayable/",
)


def _native_codex_executable() -> str:
    direct = shutil.which("codex.exe")
    if direct:
        return direct

    launcher = shutil.which("codex.cmd") or shutil.which("codex")
    if launcher:
        launcher_path = Path(launcher).resolve(strict=False)
        package_root = (
            launcher_path.parent
            / "node_modules"
            / "@openai"
            / "codex"
            / "node_modules"
        )
        candidates = sorted(
            package_root.glob(
                "@openai/codex-*/vendor/*/bin/codex.exe"
            )
        )
        if candidates:
            return str(candidates[0])
        return str(launcher_path)
    raise FileNotFoundError(
        "Codex CLI was not found on PATH"
    )


def _is_ignored_snapshot_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    return any(
        normalized.startswith(prefix)
        for prefix in _IGNORED_SNAPSHOT_PREFIXES
    )


def _snapshot(workspace: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not workspace.is_dir():
        return result
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(workspace).as_posix()
        if _is_ignored_snapshot_path(relative_path):
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(
                lambda: handle.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)
        result[relative_path] = digest.hexdigest()
    return result


def _file_changes(
    before: Mapping[str, str],
    after: Mapping[str, str],
) -> tuple[list[str], list[str], list[str]]:
    before_paths = set(before)
    after_paths = set(after)
    generated = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)
    modified = sorted(
        path
        for path in before_paths & after_paths
        if before[path] != after[path]
    )
    return generated, modified, deleted


def _parse_events(
    stdout: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    events: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    failures: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append(
                {
                    "type": "codex.stdout",
                    "text": line,
                }
            )
            continue
        if not isinstance(event, dict):
            events.append(
                {
                    "type": "codex.stdout",
                    "value": event,
                }
            )
            continue
        events.append(event)
        if event.get("type") == "turn.completed":
            event_usage = event.get("usage")
            if isinstance(event_usage, dict):
                usage = dict(event_usage)
        if event.get("type") == "turn.failed":
            error = event.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or "").strip()
            else:
                message = str(error or "").strip()
            if message:
                failures.append(message)
    return events, usage, failures


def _prompt(request: Mapping[str, Any]) -> str:
    sections = [
        "# System Instructions",
        str(request["system_prompt"]),
        "# Task",
        str(request["task_prompt"]),
    ]
    if request["mode"] == "repair":
        sections.extend(
            [
                "# Repair Instructions",
                str(request["repair_prompt"]),
            ]
        )
    sections.extend(
        [
            "# Backend Enforcement",
            (
                "Edit only files inside the requested workspace. "
                "Do not write meta.json or demo_outputs/. "
                "Do not execute engine builds, engine-native tests, "
                "runtime validation, or benchmark evaluators. "
                "The Pipeline and Evaluator own those steps."
            ),
        ]
    )
    return "\n\n".join(sections).strip() + "\n"


class CodexAgent:
    """Run one Mechanic request through `codex exec`."""

    def __init__(
        self,
        model_name: str = "",
        *,
        executable: str = "",
        timeout_sec: float | None = None,
        max_turns: int | None = 8,
        sandbox_mode: str = "workspace-write",
        extra_args: Sequence[str] = (),
        runner: Callable[..., subprocess.CompletedProcess[str]]
        | None = None,
    ) -> None:
        self.model_name = str(model_name or "").strip()
        self.executable = str(executable or "").strip()
        self.timeout_sec = timeout_sec
        self.max_turns = max_turns
        normalized_sandbox = str(sandbox_mode or "").strip().lower()
        if normalized_sandbox not in {
            "read-only",
            "workspace-write",
            "danger-full-access",
        }:
            raise ValueError(
                "sandbox_mode must be read-only, workspace-write, "
                "or danger-full-access"
            )
        self.sandbox_mode = normalized_sandbox
        self.extra_args = tuple(str(arg) for arg in extra_args)
        self._runner = runner or subprocess.run

    def _command(self, workspace: Path) -> list[str]:
        command = [
            self.executable or _native_codex_executable(),
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            self.sandbox_mode,
            "--json",
            "--color",
            "never",
            "-C",
            str(workspace),
        ]
        if self.model_name:
            command.extend(["--model", self.model_name])
        command.extend(self.extra_args)
        command.append("-")
        return command

    def run(
        self,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        normalized = validate_agent_request(request)
        workspace = Path(normalized["workspace"])
        workspace.mkdir(parents=True, exist_ok=True)
        before = _snapshot(workspace)
        command = self._command(workspace)
        status = "failed"
        returncode: int | None = None
        stdout = ""
        stderr = ""
        errors: list[str] = []

        try:
            completed = self._runner(
                command,
                cwd=workspace,
                input=_prompt(normalized),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=(
                    normalized["limits"]["timeout_sec"]
                    or self.timeout_sec
                ),
                check=False,
            )
            returncode = int(completed.returncode)
            stdout = str(completed.stdout or "")
            stderr = str(completed.stderr or "")
        except subprocess.TimeoutExpired as exc:
            status = "timed_out"
            stdout = str(exc.stdout or "")
            stderr = str(exc.stderr or "")
            errors.append(
                "Codex CLI timed out after "
                f"{normalized['limits']['timeout_sec'] or self.timeout_sec}"
                " seconds"
            )
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

        transcript, usage, event_failures = _parse_events(stdout)
        errors.extend(event_failures)
        if returncode == 0 and not event_failures:
            status = "completed"
        elif returncode is not None and not errors:
            errors.append(
                f"Codex CLI exited with code {returncode}"
            )
        if stderr.strip() and status != "completed":
            errors.append(stderr.strip())

        after = _snapshot(workspace)
        generated, modified, deleted = _file_changes(
            before,
            after,
        )
        result = {
            "ok": status == "completed",
            "request_id": normalized["request_id"],
            "status": status,
            "generated_files": generated,
            "modified_files": modified,
            "deleted_files": deleted,
            "diagnostics": [],
            "warnings": [],
            "errors": list(dict.fromkeys(errors)),
            "transcript": transcript,
            "usage": usage,
            "payload": {
                "backend": "codex",
                "model": self.model_name,
                "command": command,
                "returncode": returncode,
                "stderr": stderr,
            },
        }
        if not result["ok"] and not result["errors"]:
            result["errors"] = ["Codex CLI did not complete"]
        return validate_agent_result(
            result,
            request_id=normalized["request_id"],
            workspace=workspace,
        )
