"""
The mappings we know about, and how a new one gets made.

Retargeting needs a bone map: which bone of the clip drives which joint of the
character. This module is the registry an agent reads to answer "do I already
have one, or do I have to derive it?" — and the answer is almost always the
second one, for a reason worth stating up front.

Why a checked-in bone map is usually the wrong answer
-----------------------------------------------------
Puppeteer predicts a skeleton *per mesh* and names the joints ``joint0`` …
``jointN`` in prediction order. Those names carry no anatomy: ``joint23`` is the
hips of the one character it was predicted for, and on the next character the
same string is a shoulder or a finger. So the **target half of a bone map is
never reusable**, and a file that pins one is only valid for the single rig it
was generated against.

The **source half is different**. Mixamo always calls the hips
``mixamorig:Hips``; the UE5 mannequin always calls it ``pelvis``. That half is a
property of the library the clip came from, so it is worth writing down, and it
is what ``SOURCE_SKELETONS`` below holds.

That gives the two kinds of entry in this registry:

``SOURCE_SKELETONS``
    Reusable descriptions of where the bones of a well-known library sit,
    keyed by anatomical slot. Used to recognise an unknown clip
    (`identify_source_skeleton`), to tell an agent what it is holding, and to
    sanity-check a derived mapping.

``presets/*.json``
    Complete source-to-target maps, each **pinned to one rig**. Cheap to reuse
    when you are re-animating the same character, and actively wrong on any
    other — so `pinned_mapping_fits_rig` checks every target joint against the
    rig file before anything uses one.

Anything not covered by either is derived by ``mapping_auto``, which reads the
two skeletons' topology and geometry and needs no names at all. That is the
default path and the one the operator takes when a task names no mapping.

Reading the registry without Blender
------------------------------------
Everything here is stdlib, including the BVH hierarchy parser, so the pipeline
process and an agent can both query it. FBX bone names need Blender; ask
``mapping_auto`` instead of trying to parse the container here.

    python -m operators.gen_motion.funcs.retarget_utils.mapping_presets --list
    python -m operators.gen_motion.funcs.retarget_utils.mapping_presets \\
        --identify motion.bvh
    python -m operators.gen_motion.funcs.retarget_utils.mapping_presets \\
        --check mixamo_to_puppeteer --rig rig.txt
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .validate_mapping import load_and_validate_mapping


PRESET_DIR = Path(__file__).resolve().parent / "presets"

#: Anatomical slots, in the order a humanoid hierarchy visits them. A skeleton
#: profile may leave any of them out — Mixamo has toes, MoMask's BVH does not —
#: and matching is over the slots both sides actually fill.
SLOTS: tuple[str, ...] = (
    "hips",
    "spine",
    "spine1",
    "spine2",
    "neck",
    "head",
    "left_shoulder",
    "left_upper_arm",
    "left_forearm",
    "left_hand",
    "right_shoulder",
    "right_upper_arm",
    "right_forearm",
    "right_hand",
    "left_thigh",
    "left_shin",
    "left_foot",
    "left_toe",
    "right_thigh",
    "right_shin",
    "right_foot",
    "right_toe",
)


@dataclass(frozen=True)
class SourceSkeleton:
    """One motion library's bone naming, by anatomical slot."""

    name: str
    description: str
    bones: dict[str, str]
    notes: tuple[str, ...] = ()

    @property
    def root(self) -> str:
        return self.bones["hips"]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "root_bone": self.root,
            "slot_count": len(self.bones),
            "bones": dict(self.bones),
            "notes": list(self.notes),
        }


def _humanoid(
    *,
    hips: str,
    spine: Sequence[str],
    neck: str,
    head: str,
    shoulder: str,
    upper_arm: str,
    forearm: str,
    hand: str,
    thigh: str,
    shin: str,
    foot: str,
    toe: str | None,
    left: str,
    right: str,
    axial: str = "{}",
) -> dict[str, str]:
    """
    Build a slot table from a library's naming rule.

    Every library here names limbs as one stem plus a side affix, so the table
    is written once per library instead of forty times; ``left``/``right`` are
    format strings taking the stem (``"Left{}"``, ``"{}_l"``), and ``axial``
    is the same idea for the bones that have no side (Mixamo's ``mixamorig:``
    prefix reaches those too).
    """
    bones = {
        "hips": axial.format(hips),
        "neck": axial.format(neck),
        "head": axial.format(head),
    }
    for slot, name in zip(("spine", "spine1", "spine2"), spine):
        bones[slot] = axial.format(name)
    limbs = (
        ("shoulder", shoulder),
        ("upper_arm", upper_arm),
        ("forearm", forearm),
        ("hand", hand),
        ("thigh", thigh),
        ("shin", shin),
        ("foot", foot),
        ("toe", toe),
    )
    for slot, stem in limbs:
        if stem is None:
            continue
        bones[f"left_{slot}"] = left.format(stem)
        bones[f"right_{slot}"] = right.format(stem)
    return bones


SOURCE_SKELETONS: dict[str, SourceSkeleton] = {
    "mixamo": SourceSkeleton(
        name="mixamo",
        description=(
            "Adobe Mixamo, and every clip auto-rigged through it. The "
            "'mixamorig:' prefix makes this the easiest source to recognise."
        ),
        bones=_humanoid(
            hips="Hips",
            spine=("Spine", "Spine1", "Spine2"),
            neck="Neck",
            head="Head",
            shoulder="Shoulder",
            upper_arm="Arm",
            forearm="ForeArm",
            hand="Hand",
            thigh="UpLeg",
            shin="Leg",
            foot="Foot",
            toe="ToeBase",
            left="mixamorig:Left{}",
            right="mixamorig:Right{}",
            axial="mixamorig:{}",
        ),
        notes=(
            "Downloaded FBX is centimetre-scale; retarget with "
            "global_scale=0.01 against a metre-scale Puppeteer rig.",
            "'Without Skin' downloads carry the armature only, which is what "
            "retargeting wants.",
        ),
    ),
    "momask_bvh": SourceSkeleton(
        name="momask_bvh",
        description=(
            "The BVH this repo's own text-to-motion stage writes: HumanML3D "
            "joints exported by MoMask at 20 fps, unprefixed Mixamo names."
        ),
        bones=_humanoid(
            hips="Hips",
            spine=("Spine", "Spine1", "Spine2"),
            neck="Neck",
            head="Head",
            shoulder="Shoulder",
            upper_arm="Arm",
            forearm="ForeArm",
            hand="Hand",
            thigh="UpLeg",
            shin="Leg",
            foot="Foot",
            toe=None,
            left="Left{}",
            right="Right{}",
        ),
        notes=(
            "20 fps natively — pass that through instead of resampling, or "
            "the clip plays at the wrong speed.",
            "No toe bones: HumanML3D's 22-joint skeleton ends at the foot.",
        ),
    ),
    "cmu_bvh": SourceSkeleton(
        name="cmu_bvh",
        description=(
            "CMU Graphics Lab mocap in the widely mirrored BVH conversion "
            "(cgspeed and friends). Free, enormous, and unevenly clean."
        ),
        bones=_humanoid(
            hips="Hips",
            spine=("LowerBack", "Spine", "Spine1"),
            neck="Neck",
            head="Head",
            shoulder="Shoulder",
            upper_arm="Arm",
            forearm="ForeArm",
            hand="Hand",
            thigh="UpLeg",
            shin="Leg",
            foot="Foot",
            toe="ToeBase",
            left="Left{}",
            right="Right{}",
        ),
        notes=(
            "Inch-scale in most conversions; check the hip height before "
            "trusting root translation.",
            "Carries extra LHipJoint / LowerBack style helper bones that no "
            "slot maps to. Harmless — unmapped source bones are ignored.",
        ),
    ),
    "ue5_mannequin": SourceSkeleton(
        name="ue5_mannequin",
        description=(
            "Unreal's SK_Mannequin / Manny skeleton, which most marketplace "
            "and MetaHuman-adjacent animation ships against."
        ),
        bones=_humanoid(
            hips="pelvis",
            spine=("spine_01", "spine_02", "spine_03"),
            neck="neck_01",
            head="head",
            shoulder="clavicle",
            upper_arm="upperarm",
            forearm="lowerarm",
            hand="hand",
            thigh="thigh",
            shin="calf",
            foot="foot",
            toe="ball",
            left="{}_l",
            right="{}_r",
        ),
        notes=(
            "Centimetre-scale and Z-up; Blender's FBX importer converts on "
            "the way in, so retarget in metres as usual.",
            "A 'root' bone sits under the pelvis. Leave it unmapped and let "
            "root translation come from the hips.",
        ),
    ),
    "smplx": SourceSkeleton(
        name="smplx",
        description=(
            "SMPL / SMPL-X joint naming, which most motion-research code and "
            "AMASS-derived datasets emit."
        ),
        bones=_humanoid(
            hips="pelvis",
            spine=("spine1", "spine2", "spine3"),
            neck="neck",
            head="head",
            shoulder="collar",
            upper_arm="shoulder",
            forearm="elbow",
            hand="wrist",
            thigh="hip",
            shin="knee",
            foot="ankle",
            toe="foot",
            left="left_{}",
            right="right_{}",
        ),
        notes=(
            "The names are off by one against every other convention here: "
            "SMPL's 'left_shoulder' is the upper arm and 'left_foot' is the "
            "toe. The slot table already accounts for that.",
        ),
    ),
}


# ── source skeleton identification ────────────────────────────────────────────


def _normalise(name: str) -> str:
    """Fold the spelling differences that are never semantic."""
    text = name.strip().lower()
    for prefix in ("mixamorig:", "mixamorig1:", "mixamorig_"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return "".join(ch for ch in text if ch.isalnum())


def identify_source_skeleton(
    bone_names: Iterable[str],
) -> tuple[str | None, float]:
    """
    Name the library a set of bone names came from, with a confidence.

    Scored as the fraction of a profile's slots whose bone is present, so a
    skeleton carrying extra bones is not penalised — CMU's helper joints and
    Mixamo's fingers are exactly that. Below 0.6 nothing is claimed, because a
    half-match is worse than admitting the clip is unknown: it would send
    retargeting to a preset built for another skeleton.
    """
    present = {_normalise(name) for name in bone_names}
    if not present:
        return None, 0.0
    best_name, best_score = None, 0.0
    for profile in SOURCE_SKELETONS.values():
        wanted = {_normalise(bone) for bone in profile.bones.values()}
        score = len(wanted & present) / len(wanted)
        if score > best_score:
            best_name, best_score = profile.name, score
    if best_score < 0.6:
        return None, round(best_score, 3)
    return best_name, round(best_score, 3)


def read_bvh_bone_names(path: str | Path) -> list[str]:
    """
    Bone names from a BVH hierarchy, without Blender.

    BVH is text and its hierarchy is a prefix of the file, so identifying a
    clip costs a few kilobytes rather than a Blender start-up. Reading stops at
    ``MOTION``; the sample block below it can be hundreds of megabytes.
    """
    names: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            token = line.split()
            if not token:
                continue
            head = token[0].upper()
            if head == "MOTION":
                break
            if head in {"ROOT", "JOINT"} and len(token) > 1:
                names.append(token[1])
    return names


def identify_motion_file(path: str | Path) -> dict:
    """Identify a clip's source skeleton, as far as the format allows."""
    motion = Path(path)
    suffix = motion.suffix.lower()
    if suffix != ".bvh":
        return {
            "path": str(motion),
            "format": suffix.lstrip("."),
            "skeleton": None,
            "confidence": 0.0,
            "bone_count": None,
            "reason": (
                "Only BVH can be read without Blender. Derive the mapping "
                "with mapping_auto, which reads the FBX in a bpy subprocess."
            ),
        }
    bones = read_bvh_bone_names(motion)
    name, confidence = identify_source_skeleton(bones)
    return {
        "path": str(motion),
        "format": "bvh",
        "skeleton": name,
        "confidence": confidence,
        "bone_count": len(bones),
        "reason": (
            None
            if name
            else "No known profile matched; mapping_auto will derive one."
        ),
    }


# ── pinned mappings ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PinnedMapping:
    """A complete bone map, valid only for the rig it was generated against."""

    name: str
    path: Path
    source_skeleton: str
    target_skeleton: str
    description: str
    bone_count: int
    chains: tuple[str, ...]
    target_joints: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "source_skeleton": self.source_skeleton,
            "target_skeleton": self.target_skeleton,
            "description": self.description,
            "bone_count": self.bone_count,
            "chains": list(self.chains),
            "reusable": False,
        }


def list_pinned_mappings() -> list[PinnedMapping]:
    """Every mapping in ``presets/``, sorted by name."""
    presets = []
    for path in sorted(PRESET_DIR.glob("*.json")):
        try:
            data = normalise_mapping(
                json.loads(path.read_text(encoding="utf-8-sig"))
            )
        except (OSError, ValueError):
            continue
        bone_map = data.get("bone_map", {})
        presets.append(
            PinnedMapping(
                name=path.stem,
                path=path,
                source_skeleton=str(data.get("source_skeleton", "unknown")),
                target_skeleton=str(data.get("target_skeleton", "unknown")),
                description=str(data.get("description", "")),
                bone_count=len(bone_map),
                chains=tuple(sorted(data.get("retarget_chains", {}))),
                target_joints=tuple(sorted(set(bone_map.values()))),
            )
        )
    return presets


def find_pinned_mapping(name: str) -> PinnedMapping:
    """Look up one mapping by file stem, listing the alternatives on a miss."""
    presets = list_pinned_mappings()
    for preset in presets:
        if preset.name == name:
            return preset
    available = ", ".join(preset.name for preset in presets) or "<none>"
    raise KeyError(
        f"Unknown retarget mapping preset {name!r}. Available: {available}"
    )


def normalise_mapping(data: dict) -> dict:
    """
    Accept the older key spellings without carrying them any further.

    The first mappings written here said ``mixamo`` where they meant "the
    source", back when Mixamo was the only source. Readers should only ever see
    ``source``, so the rename happens once, on load.
    """
    result = dict(data)
    roots = dict(result.get("root_bones") or {})
    if "source" not in roots:
        for legacy in ("mixamo", "src"):
            if legacy in roots:
                roots["source"] = roots.pop(legacy)
                break
    if "puppeteer" not in roots and "target" in roots:
        roots["puppeteer"] = roots["target"]
    if roots:
        result["root_bones"] = roots

    chains = {}
    for chain_name, chain in (result.get("retarget_chains") or {}).items():
        chain = dict(chain)
        if "source" not in chain:
            for legacy in ("mixamo", "src"):
                if legacy in chain:
                    chain["source"] = chain.pop(legacy)
                    break
        chains[chain_name] = chain
    if chains:
        result["retarget_chains"] = chains
    return result


def load_pinned_mapping(name: str) -> dict:
    """Load and validate one preset, with legacy keys already renamed."""
    preset = find_pinned_mapping(name)
    return normalise_mapping(load_and_validate_mapping(preset.path))


def read_rig_joint_names(rig_path: str | Path) -> list[str]:
    """Joint names from a Puppeteer ``.txt`` rig, without Blender."""
    names = []
    with open(rig_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            token = line.split()
            if len(token) >= 2 and token[0] == "joints":
                names.append(token[1])
    return names


def pinned_mapping_fits_rig(name: str, rig_path: str | Path) -> dict:
    """
    Decide whether a pinned mapping may be used against a given rig.

    Every target joint has to exist in the rig file. A partial match is a
    rejection, not a warning: Puppeteer's joint names are positional, so a
    mapping that resolves half its joints is not half right — it is driving the
    wrong body parts with a straight face.
    """
    preset = find_pinned_mapping(name)
    available = set(read_rig_joint_names(rig_path))
    missing = sorted(set(preset.target_joints) - available)
    return {
        "preset": name,
        "rig": str(rig_path),
        "fits": not missing,
        "missing_target_joints": missing[:12],
        "missing_count": len(missing),
    }


def resolve_mapping(
    *,
    preset: str | None,
    target_rig_path: str | Path,
) -> str | None:
    """
    Turn a task's ``mapping_preset`` into a file path, or ``None`` for auto.

    ``None`` in, ``None`` out — the caller then derives the mapping, which is
    the normal path. A named preset that does not fit the rig raises rather
    than silently falling back, because a task that named one wanted that one.
    """
    if not preset:
        return None
    fit = pinned_mapping_fits_rig(preset, target_rig_path)
    if not fit["fits"]:
        raise ValueError(
            f"Mapping preset {preset!r} does not fit this rig: "
            f"{fit['missing_count']} of its target joints are absent "
            f"(e.g. {fit['missing_target_joints']}). Presets are pinned to "
            "one Puppeteer rig; omit mapping_preset to derive a mapping for "
            "this character instead."
        )
    return str(find_pinned_mapping(preset).path)


def registry() -> dict:
    """The whole registry as plain data, for an agent or a report."""
    return {
        "source_skeletons": [
            profile.as_dict() for profile in SOURCE_SKELETONS.values()
        ],
        "pinned_mappings": [
            preset.as_dict() for preset in list_pinned_mappings()
        ],
        "default_strategy": (
            "Derive with mapping_auto. Pinned mappings only apply to the rig "
            "they were generated against; source skeleton profiles describe "
            "the clip side only."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the registry as JSON.",
    )
    parser.add_argument(
        "--identify",
        default=None,
        help="Name the source skeleton of a BVH clip.",
    )
    parser.add_argument(
        "--check",
        default=None,
        help="Preset name to test against --rig.",
    )
    parser.add_argument(
        "--rig",
        default=None,
        help="Puppeteer rig .txt that --check tests against.",
    )
    args = parser.parse_args()

    if args.check:
        if not args.rig:
            parser.error("--check also needs --rig")
        payload = pinned_mapping_fits_rig(args.check, args.rig)
    elif args.identify:
        payload = identify_motion_file(args.identify)
    else:
        payload = registry()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


__all__ = [
    "PinnedMapping",
    "SLOTS",
    "SOURCE_SKELETONS",
    "SourceSkeleton",
    "find_pinned_mapping",
    "identify_motion_file",
    "identify_source_skeleton",
    "list_pinned_mappings",
    "load_pinned_mapping",
    "normalise_mapping",
    "pinned_mapping_fits_rig",
    "read_bvh_bone_names",
    "read_rig_joint_names",
    "registry",
    "resolve_mapping",
]
