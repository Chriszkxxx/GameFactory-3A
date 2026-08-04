"""Mechanic Agent backends and JSON-serializable contracts."""

from .contracts import (
    REQUEST_MODES,
    RESULT_STATUSES,
    resolve_workspace_file,
    validate_agent_request,
    validate_agent_result,
)
from .codex import CodexAgent
from .stub import StubAgent, make_stub_mechanic_files

__all__ = [
    "CodexAgent",
    "REQUEST_MODES",
    "RESULT_STATUSES",
    "StubAgent",
    "make_stub_mechanic_files",
    "resolve_workspace_file",
    "validate_agent_request",
    "validate_agent_result",
]
