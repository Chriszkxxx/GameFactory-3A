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
]
