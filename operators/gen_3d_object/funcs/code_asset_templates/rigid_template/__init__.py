"""拼接刚体 — subjects built by joining rigid parts side by side.

Claims the COMPOSED topology: a receiver plus a barrel plus a magazine, a body
plus four wheels. Nothing has to exist before anything else, so the whole
subject is describable and the route is `code`.

WHY THE WORDS LIVE HERE. They used to be a `hard_surface` tuple in a central
lexicon, which meant a project with its own rigid nouns had to edit a file it
did not own. They belong beside the mechanism that builds what they name:
:mod:`..assembly` chains and groups the parts, and this module is what says
"that subject is one of these". A new rigid domain registers its own strategy
with its own words and never touches this one.

DELIBERATELY THIN. The mechanism is general; part lists are not. A rifle's
chamber diameter and a car's wheelbase are content belonging to the build that
wants them, so no part tables are shipped here — worked chains live in
`test/test_3d_object_spec.py`, which is also where they get exercised.
"""

from __future__ import annotations

from .. import routing
from ..assembly import chain, group, mirrored

__all__ = ["MATERIALS", "SHAPES", "THINGS", "claim", "chain", "group", "mirrored"]

#: Objects that are assemblies of rigid parts. Matched as whole words, so
#: "rail" does not fire inside "railing" — the two want different assemblies.
THINGS = (
    "crate", "box", "barrel", "chest", "container",
    "sign", "signpost", "post", "pole", "fence", "railing", "rail",
    "wheel", "gear", "cog", "pipe", "tube", "beam", "girder",
    "sword", "blade", "knife", "axe", "hammer", "rifle", "pistol",
    "gun", "weapon", "shield", "helmet", "helm", "armour", "armor",
    "cuirass", "breastplate", "pauldron", "gauntlet", "greave", "greaves",
    "vambrace", "bracer", "sabaton", "spear", "lance", "bow",
    "table", "chair", "bench", "desk", "shelf", "door", "window",
    "lamp", "lantern", "torch", "crystal", "gem", "coin", "key",
    "wall", "pillar", "column", "arch", "stair", "platform", "ramp",
    "vehicle", "car", "cart", "wagon", "turret", "antenna", "drone",
    "golem", "robot", "mech", "construct", "statue", "machine", "engine",
)

#: Materials that imply a manufactured object. Weaker evidence than a noun —
#: "steel" says what something is made of, not what it is — but they are what
#: tip a borderline subject: a "stone golem" is a stack of blocks, and without
#: these a single organic word decided it unopposed.
MATERIALS = (
    "stone", "metal", "steel", "iron", "wood", "wooden", "plank", "brick",
    "brass", "bronze", "copper", "concrete", "plastic", "carbon",
)

#: Shapes that describe an assembly rather than name one. Same weight as a
#: material: "chamfered" and "turned" are how the rifle variants differ.
SHAPES = (
    "chamfered", "turned", "bevelled", "beveled", "segmented", "modular",
    "plated", "riveted", "welded", "bolted",
)


def claim(subject: str, asset_type: str = "prop") -> routing.Claim | None:
    """Claim ``subject`` as an assembly of rigid parts, or decline.

    Strength is the count of matched words, which is only ever compared against
    another evidence-tier claim — see :func:`..routing.resolve`. Materials and
    shape words count the same as nouns because that is what made "stone golem
    creature" come out honestly ambiguous instead of routed on one word.
    """

    seen = routing.words(f"{subject} {asset_type}")
    things = tuple(word for word in THINGS if word in seen)
    materials = tuple(word for word in MATERIALS if word in seen)
    shapes = tuple(word for word in SHAPES if word in seen)

    evidence = things + materials + shapes
    if not evidence:
        return None

    return routing.Claim(
        topology=routing.COMPOSED,
        strength=float(len(evidence)),
        evidence=evidence,
        builder="operators.gen_3d_object.funcs.code_asset_templates.rigid_template",
        reason=(
            f"{subject!r} reads as an assembly of rigid parts "
            f"({', '.join(evidence)}): exactly describable, so a spec gives a "
            "named-part mesh with a stated size and facing. Join the parts with "
            "`assembly.chain` or `assembly.group` rather than absolute "
            "positions — a solved relation does not go stale when a neighbour "
            "changes size."
        ),
    )


routing.register("rigid", claim)
