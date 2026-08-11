"""
The four steps a motion task is built from.

One file per step, each one a plain function over explicit arguments: rig a
mesh, generate a clip from text, bring a clip in from an external library, and
retarget a clip onto a rig. ``operator.py`` sequences them; none of them knows
about the others, so a task can use any subset.

``retarget_utils/`` is the exception to "one file per step" — retargeting is a
Blender program, and the modules under there run in a ``bpy`` interpreter that
this process cannot import. ``retarget_motion`` is the host-side driver that
runs them as subprocesses, so it is the only thing here that needs importing.
"""

from importlib import import_module
from typing import Any

#: Exported name -> module it lives in. Resolved on first access rather than
#: at import, because the ``bpy`` subprocess reaches ``retarget_utils`` through
#: this package: eagerly importing every sibling would make a Blender module
#: pull in the host-side subprocess driver it is being run by.
_EXPORTS = {
    "fetch_motion": "fetch_motion",
    "list_motion_sources": "fetch_motion",
    "suggest_global_scale": "fetch_motion",
    "generate_motion": "generate_motion",
    "retarget_motion": "retarget_motion",
    "rig_character": "rig_character",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(f".{module}", __name__), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
