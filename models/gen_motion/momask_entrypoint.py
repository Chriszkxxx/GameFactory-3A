"""Compatibility entrypoint for the pinned MoMask inference script."""

from __future__ import annotations

import runpy
import sys
from collections.abc import Iterable
from pathlib import Path


def _artist_list_setter(name: str, add_method: str):
    def setter(axes, values: Iterable[object]) -> None:
        for artist in list(getattr(axes, name)):
            artist.remove()
        add = getattr(axes, add_method)
        for artist in values:
            add(artist)

    return setter


def _install_matplotlib_compatibility() -> None:
    # MoMask was released with Matplotlib 3.1.3 and clears 3D artists through
    # ``ax.lines = []`` and ``ax.collections = []``.  CPython 3.10 wheels start
    # at Matplotlib 3.5, where both attributes became read-only ArtistLists.
    from matplotlib.axes import Axes

    for name, add_method in (
        ("lines", "add_line"),
        ("collections", "add_collection"),
    ):
        descriptor = getattr(Axes, name)
        if isinstance(descriptor, property) and descriptor.fset is None:
            setattr(
                Axes,
                name,
                descriptor.setter(_artist_list_setter(name, add_method)),
            )


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: momask_entrypoint.py <gen_t2m.py> [args ...]")
    script = Path(sys.argv.pop(1)).expanduser().resolve()
    sys.path.insert(0, str(script.parent))
    _install_matplotlib_compatibility()
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
