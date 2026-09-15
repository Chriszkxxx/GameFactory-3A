"""Templates the code-asset route reads, organised by how a subject assembles.

The organising axis is assembly topology, because that is what decides the
route. A rifle and a suit of armour are both hard-surfaced and route
differently:

* **Composition** — parts sit beside each other, joined by adjacency. A rifle,
  a car. Nothing has to exist first, so it is fully describable: `code`.
* **Nesting** — layers sit on a host that must exist and be measured first.
  Armour on a body. The host is generated and the layers stated: the hybrid
  route.

That axis is `routing.COMPOSED` and `routing.NESTED`, with `routing.SURFACE`
for subjects that are not assemblies at all.

LAYOUT

``routing``
    The mechanism, and nothing domain-specific: `Claim`, the registry, and how
    competing claims resolve. Contains no vocabulary.
``compose``
    Parts plus materials into a spec. Used by every route.
``assembly``
    Joining parts by `attach` — chain, group, mirror. Used by composed
    subjects.
``rigid_template``
    拼接刚体: claims composition. Its own vocabulary, no part tables.
``human_template``
    Figures and what they wear: claims nesting. Its own vocabulary, plus the
    anatomy, measuring and fitting.
``surface``
    Claims subjects with no assembly. A strategy only — it has nothing to
    build, so it is not a `_template` package.

ADDING A DOMAIN is adding a package: register a strategy that claims what it
can build, ship the templates that build it, and change nothing here or in
`code_asset`:

    routing.register("submarine", claim)
    suits_code_asset("submarine")     # -> code, claimed_by="submarine"

Importing this package registers the three shipped strategies. `code_asset`
imports it for exactly that reason, so `suits_code_asset` has something to ask.
"""

from __future__ import annotations

from . import assembly, compose, human_template, rigid_template, routing, surface

__all__ = [
    "assembly",
    "compose",
    "human_template",
    "rigid_template",
    "routing",
    "surface",
    "fit_wearable",
]


def fit_wearable(*, body: str, clothing: str, output: str,
                 coverage: str = "full_body", sleeve_pose: str = "down",
                 footwear_mode: str = "preserve", height_metres: float = 1.75,
                 clearance_metres: float = 0.008, headwear_offset_metres: float = 0.0,
                 blender_python: str | None = None, source_heights: dict[str, float] | None = None,
                 clothing_rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
                 save_blend: bool = True, timeout: float = 600.0):
    """Load the wearable worker only when requested."""
    from .human_template.wearable_fit import fit_wearable as worker
    return worker(body=body, clothing=clothing, output=output, coverage=coverage,
                  sleeve_pose=sleeve_pose, footwear_mode=footwear_mode,
                  height_metres=height_metres, clearance_metres=clearance_metres,
                  headwear_offset_metres=headwear_offset_metres,
                  blender_python=blender_python, source_heights=source_heights,
                  clothing_rotation=clothing_rotation, save_blend=save_blend,
                  timeout=timeout)
