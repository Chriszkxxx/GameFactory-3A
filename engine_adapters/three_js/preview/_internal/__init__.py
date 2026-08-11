"""Private preview implementation for the three.js adapter.

Rendering needs ``numpy`` and ``Pillow``; naming a view does not. The
split is enforced here with a module-level ``__getattr__``, so importing
this package — which ``ThreeClient`` does transitively — costs nothing but
``views.py``, and the heavy modules load on first use.

That matters because the launchers run under a conda environment
provisioned for the Node toolchain, whose Python is the standard library
and nothing else. An adapter that could not be imported there would break
every script in ``scripts/three_js/``.
"""

from typing import Any

from .views import (
    DEFAULT_VIEW_SET,
    HORIZONTAL_VIEW_AXES,
    SUPPORTED_VIEW_AXES,
    VIEW_AXES,
    VIEW_CONVENTION,
    VIEW_SCREEN_RIGHT,
    VIEW_SETS,
    label_for,
    resolve_axes,
)

#: name -> submodule that defines it, imported on first attribute access.
_LAZY_EXPORTS = {
    "Geometry": "gltf_geometry",
    "GeometryUnavailable": "gltf_geometry",
    "Surface": "gltf_geometry",
    "load_geometry": "gltf_geometry",
    "render_view": "rasterizer",
    "render_views": "rasterizer",
    "sample_geometry": "rasterizer",
    "label_image": "sheet",
    "sheet_title": "sheet",
    "write_contact_sheet": "sheet",
    "write_views": "sheet",
}

__all__ = [
    "DEFAULT_VIEW_SET",
    "HORIZONTAL_VIEW_AXES",
    "SUPPORTED_VIEW_AXES",
    "VIEW_AXES",
    "VIEW_CONVENTION",
    "VIEW_SCREEN_RIGHT",
    "VIEW_SETS",
    "label_for",
    "resolve_axes",
    *sorted(_LAZY_EXPORTS),
    "require_backend",
]


def require_backend() -> None:
    """Import the render backend now, so a caller can report its absence.

    Without this, a missing ``numpy`` would surface as an ``ImportError``
    from the middle of an attribute access, which is neither catchable at
    a sensible place nor informative to whoever ran the operation.
    """

    from . import gltf_geometry, rasterizer, sheet  # noqa: F401


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )
    from importlib import import_module

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
