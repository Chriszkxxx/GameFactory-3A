#!/usr/bin/env python3
"""Auto-generate a Mixamo -> Puppeteer bone mapping from skeleton topology + geometry.

No hardcoded joint indices. Both armatures are inspected structurally:

  * HIPS  = multi-child bone with the biggest subtree (pelvis hub)
  * legs vs spine = HIPS children split by world-Z relative to HIPS
  * chest = first multi-child junction walking up the spine
  * neck/arms = chest children, neck is highest-Z, the other two are shoulders
  * left/right = resolved by world-X sign AFTER applying Mixamo's 180-deg Z
    facing-fix, so both rigs live in one shared frame
  * limb chains = walk single-child descendants until we hit a branch
    (hand stops naturally at 5-finger fan-out; foot stops at toe)

Two ways to generate a mapping (both structural, no hardcoded joint indices):

  Mode A — FBX pair: a Puppeteer bind-pose FBX + a Mixamo FBX.
  Mode B — motion + rig: a source motion (`.bvh`/`.fbx`) + a Puppeteer-rigged
           GLB (`--glb` + `--rig`). The target skeleton is built straight from
           the rig, so *no pre-exported Puppeteer FBX is needed* — this is the
           "just BVH + GLB" path used when `retarget_motion` gets no mapping.

Vendored from Puppeteer's `skeleton_retarget_refine_code5/tools/`. Requires a
`bpy`-capable interpreter (`pip install bpy==4.2.0`) or Blender's bundled
Python. Run as a package module so the relative imports resolve::

    # Mode A (FBX pair)
    python -m engine_adapters.blender.mappings.generate_mapping_auto \\
        --puppeteer-fbx char_puppeteer_ue.fbx \\
        --mixamo-fbx    any_mixamo_char.fbx \\
        --output        mappings/my_mapping.json

    # Mode B (motion + rig -> mapping)
    python -m engine_adapters.blender.mappings.generate_mapping_auto \\
        --glb char.glb \\
        --rig char_skin.txt \\
        --source-anim motion.bvh \\
        --output mappings/momask_to_char.json

The result drops into `world_delta.py --mapping`; the presets in `presets/` are
known-good outputs of the same two modes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import bpy
from mathutils import Matrix, Vector

# NOTE: Despite the old hardcoded mapping's comment claiming the two rigs
# face opposite directions and need a 180-deg Z fix, real data shows BOTH
# Puppeteer (joint17/34 toe tails at Y<0) and Mixamo (toe tails at Y<0) face
# -Y in world space. Applying any flip is what caused the original leg-mirror
# and arm-swap bugs. We compare raw world-X directly.
FRAME_FIX = Matrix.Identity(4)

# ---------------------------------------------------------------- bpy utils ---


def clear_scene() -> None:
    for d in (bpy.data.objects, bpy.data.armatures, bpy.data.meshes,
              bpy.data.actions, bpy.data.materials):
        for x in list(d):
            d.remove(x, do_unlink=True)


def import_fbx_armature(path: str, name: str) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    arm = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
    arm.name = name
    return arm


def whead(arm: bpy.types.Object, name: str) -> Vector:
    return arm.matrix_world @ arm.data.bones[name].head_local


# ----------------------------------------------------- topology helpers ---


def subtree_size(arm: bpy.types.Object, name: str, cache: Dict[str, int]) -> int:
    if name in cache:
        return cache[name]
    s = 1 + sum(subtree_size(arm, c.name, cache) for c in arm.data.bones[name].children)
    cache[name] = s
    return s


def find_hips(arm: bpy.types.Object) -> str:
    """Largest subtree among multi-child junctions; falls back to bone with most children."""
    cache: Dict[str, int] = {}
    multi = [b.name for b in arm.data.bones if len(b.children) >= 3]
    if not multi:
        multi = [b.name for b in arm.data.bones if len(b.children) >= 2]
    if not multi:
        # Pathological; pick the root.
        return next(b.name for b in arm.data.bones if b.parent is None)
    return max(multi, key=lambda n: subtree_size(arm, n, cache))


def walk_chain(arm: bpy.types.Object, start: str, max_len: int = 64) -> List[str]:
    """Follow single-child descendants from `start` until branch or leaf."""
    chain = [start]
    cur = arm.data.bones[start]
    while len(chain) < max_len and len(cur.children) == 1:
        cur = cur.children[0]
        chain.append(cur.name)
    return chain


def first_branch(arm: bpy.types.Object, start: str) -> Optional[str]:
    """First descendant (inclusive) with >= 2 children. None if leaf reached."""
    cur = arm.data.bones[start]
    while True:
        if len(cur.children) >= 2:
            return cur.name
        if not cur.children:
            return None
        cur = cur.children[0]


# ---------------------------------------------------- structural classify ---


def classify(arm: bpy.types.Object, fix: Matrix) -> Dict[str, object]:
    """Return roles for one armature:
        hips:   str
        spine:  List[str]   (hips ... head/neck-tip)
        legs:   Tuple[List[str], List[str]]
        arms:   Tuple[List[str], List[str]]

    NOTE: For hub bones (joint23-style) all children share the same head,
    so we classify by each child's *chain tip* head position, not by the
    child's own head.
    """
    bones = arm.data.bones

    def fpos(n: str) -> Vector:
        return fix @ whead(arm, n)

    def tip_of(start: str) -> str:
        """End of the single-child chain starting at `start` (or first branch)."""
        return walk_chain(arm, start)[-1]

    def tip_pos(start: str) -> Vector:
        return fpos(tip_of(start))

    hips = find_hips(arm)
    hp = fpos(hips)
    hc = [c.name for c in bones[hips].children]

    # Split hips children by direction of their CHAIN TIP relative to hips:
    #   tip above hips -> spine root
    #   tip below hips -> leg root
    legs_root = [n for n in hc if tip_pos(n).z < hp.z]
    spine_cands = [n for n in hc if tip_pos(n).z >= hp.z]
    if not spine_cands:
        spine_cands = [max(hc, key=lambda n: tip_pos(n).z)]
        legs_root = [n for n in hc if n not in spine_cands]
    # If multiple "spine candidates" (e.g., extra helper bones), pick the one
    # whose chain tip is highest.
    spine_root = max(spine_cands, key=lambda n: tip_pos(n).z)

    # Walk spine until first branch (chest).
    chest = first_branch(arm, spine_root)
    pre_chest: List[str] = []
    cur = bones[spine_root]
    while cur.name != (chest or cur.name):
        pre_chest.append(cur.name)
        cur = cur.children[0]
    if chest:
        pre_chest.append(chest)

    arms_root: List[str] = []
    neck_chain: List[str] = []
    if chest:
        cc = [c.name for c in bones[chest].children]
        # Chest children share head too -> classify by chain tip:
        #   neck/head tip is highest in Z; arms tips spread out in |X|.
        neck_root = max(cc, key=lambda n: tip_pos(n).z)
        arms_root = [n for n in cc if n != neck_root]
        neck_chain = walk_chain(arm, neck_root)
    else:
        neck_chain = walk_chain(arm, spine_root)
        pre_chest = []

    # Sort arms/legs by chain-tip X (not root X, which is shared on hub).
    legs_root.sort(key=lambda n: tip_pos(n).x)
    arms_root.sort(key=lambda n: tip_pos(n).x)

    leg_chains = tuple(walk_chain(arm, r)[:4] for r in legs_root[:2])
    arm_chains = tuple(walk_chain(arm, r)[:4] for r in arms_root[:2])

    spine_full = [hips] + pre_chest + neck_chain
    return {
        "hips": hips,
        "spine": spine_full,
        "legs": leg_chains,
        "arms": arm_chains,
    }


# ---------------------------------------------------------- mapping build ---


def left_sign_from_mixamo(mix_arm: bpy.types.Object) -> int:
    """Return +1 or -1: world-X sign that corresponds to character-LEFT,
    derived from Mixamo's named bones (LeftUpLeg is at the LEFT side)."""
    hips = whead(mix_arm, "mixamorig:Hips")
    lup = whead(mix_arm, "mixamorig:LeftUpLeg")
    return 1 if (lup.x - hips.x) >= 0 else -1


def split_lr(chains: Tuple[List[str], List[str]],
             arm: bpy.types.Object, fix: Matrix,
             left_sign: int) -> Tuple[List[str], List[str]]:
    """Return (left_chain, right_chain). Use the CHAIN TIP X (not the root X,
    which on a hub like joint23 is shared between both sides)."""
    if not chains:
        return [], []
    a, b = chains[0], chains[1] if len(chains) > 1 else []
    if not b:
        return (a, []) if left_sign > 0 else ([], a)
    ax = (fix @ whead(arm, a[-1])).x
    bx = (fix @ whead(arm, b[-1])).x
    return (a, b) if ax * left_sign > bx * left_sign else (b, a)


def resolve_left_sign(src_arm: bpy.types.Object,
                      left_sign: Optional[int]) -> int:
    """Resolve the world-X sign that means character-LEFT for the source rig.

    When `left_sign` is given it is used verbatim. Otherwise we try Mixamo's
    named bones (`mixamorig:*`); any other rig (e.g. a BVH from MoMask) falls
    back to +1. This only affects the *labels* in `retarget_chains` — the actual
    bone pairing is unaffected, because the same sign is applied to both source
    and target, keeping their sides consistent.
    """
    if left_sign is not None:
        return left_sign
    try:
        return left_sign_from_mixamo(src_arm)
    except Exception:
        return 1


def build_mapping(src_arm: bpy.types.Object,
                  dst_arm: bpy.types.Object,
                  left_sign: Optional[int] = None
                  ) -> Tuple[Dict[str, str], Dict[str, dict], str, str]:
    """Infer a source->Puppeteer bone map from skeleton topology + geometry.

    Works for any source rig (Mixamo FBX or a BVH such as MoMask) because the
    classification is structural, not name-based.

    Returns: (bone_map, retarget_chains, source_root, puppeteer_root).
    """
    # Both rigs are inspected in raw world space (no facing flip).
    src = classify(src_arm, Matrix.Identity(4))
    dst = classify(dst_arm, Matrix.Identity(4))

    left_sign = resolve_left_sign(src_arm, left_sign)
    mL, mR = split_lr(src["legs"], src_arm, Matrix.Identity(4), left_sign)
    pL, pR = split_lr(dst["legs"], dst_arm, Matrix.Identity(4), left_sign)
    maL, maR = split_lr(src["arms"], src_arm, Matrix.Identity(4), left_sign)
    paL, paR = split_lr(dst["arms"], dst_arm, Matrix.Identity(4), left_sign)

    def zip_chain(s: List[str], d: List[str]) -> List[Tuple[str, str]]:
        n = min(len(s), len(d))
        return list(zip(s[:n], d[:n]))

    pairs: List[Tuple[str, str]] = []
    pairs += zip_chain(src["spine"], dst["spine"])
    pairs += zip_chain(maL, paL)
    pairs += zip_chain(maR, paR)
    pairs += zip_chain(mL, pL)
    pairs += zip_chain(mR, pR)

    bone_map: Dict[str, str] = {}
    for s, d in pairs:
        bone_map.setdefault(s, d)

    chains = {
        "spine":     {"source": src["spine"], "puppeteer": dst["spine"]},
        "left_arm":  {"source": maL,          "puppeteer": paL},
        "right_arm": {"source": maR,          "puppeteer": paR},
        "left_leg":  {"source": mL,           "puppeteer": pL},
        "right_leg": {"source": mR,           "puppeteer": pR},
    }
    # Trim chains to the shortest of each pair so JSON is consistent with bone_map.
    for v in chains.values():
        n = min(len(v["source"]), len(v["puppeteer"]))
        v["source"] = v["source"][:n]
        v["puppeteer"] = v["puppeteer"][:n]

    return bone_map, chains, str(src["hips"]), str(dst["hips"])


# -------------------------------------------------------------- output ---


def write_json(path: str, bone_map: Dict[str, str], chains: Dict[str, dict],
               src_root: str, pup_root: str, source_label: str = "Mixamo",
               origin: str = "FBX topology") -> None:
    payload = {
        "description": f"{source_label} (source) -> Puppeteer (target). "
                       f"Auto-generated from {origin}.",
        "source_skeleton": source_label,
        "target_skeleton": "Puppeteer",
        "root_bones": {"source": src_root, "puppeteer": pup_root},
        "bone_map": bone_map,
        "retarget_chains": chains,
        "notes": [
            "Mapping inferred by walking hierarchies + world-pose geometry; no joint indices hardcoded.",
            "Left/right labels follow the source rig's world-X sign; bone pairing is side-consistent regardless.",
            "Chain length = min(source, puppeteer) so bone_map and retarget_chains stay consistent.",
        ],
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


# ------------------------------------------------ motion-based generation ---


def generate_from_motion(glb: str, rig: str, source_anim: str, output: str,
                         global_scale: float = 1.0,
                         left_sign: Optional[int] = None) -> None:
    """Generate a mapping straight from a motion clip + a Puppeteer-rigged GLB.

    This is the "just BVH + GLB" entry point: the Puppeteer *target* skeleton is
    built directly from `glb` + `rig` (no pre-exported FBX needed), the *source*
    skeleton comes from the motion file (`.bvh` for MoMask or `.fbx` for Mixamo),
    and the mapping is inferred structurally. The output JSON is directly
    consumable by `world_delta` / `PuppeteerModel.retarget(mapping=...)`.
    """
    # Reuse the exact rig/animation importers used by the retarget engine so the
    # generated mapping matches how bones are actually posed at retarget time.
    from ..world_delta import build_puppeteer_rig, import_source_animation
    from ..rig_io import clear_bpy_data

    clear_bpy_data()
    print(f"[1/4] Building Puppeteer target from GLB + rig:\n  glb={glb}\n  rig={rig}")
    _, dst_arm = build_puppeteer_rig(glb, rig)
    dst_arm.name = "Puppeteer"

    ext = os.path.splitext(source_anim)[1].lower()
    label = "BVH" if ext == ".bvh" else "Mixamo"
    print(f"[2/4] Importing source motion ({ext or 'fbx'}): {source_anim}")
    src_arm, _ = import_source_animation(source_anim, global_scale=global_scale)
    src_arm.hide_viewport = False  # ensure bones are readable
    src_arm.name = "Source"
    bpy.context.scene.frame_set(int(bpy.context.scene.frame_start))

    print("[3/4] Inferring mapping from topology + geometry...")
    bone_map, chains, src_root, pup_root = build_mapping(src_arm, dst_arm, left_sign)
    print(f"  matched {len(bone_map)} bones; roots: {src_root} -> {pup_root}")
    for k, v in chains.items():
        print(f"    {k:10s} ({len(v['source']):d}): {v['source']}  ->  {v['puppeteer']}")

    print(f"[4/4] Writing mapping: {output}")
    write_json(output, bone_map, chains, src_root, pup_root,
               source_label=label, origin=f"{label} motion + Puppeteer rig topology")
    print(f"Wrote: {output}")


# --------------------------------------------------------------- entry ---


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    # Mode A: FBX pair (Puppeteer bind-pose FBX + Mixamo FBX).
    p.add_argument("--puppeteer-fbx",
                   help="Puppeteer bind-pose FBX (mode A: FBX pair).")
    p.add_argument("--mixamo-fbx",
                   help="Mixamo FBX (mode A). Animation or T-pose; first frame is the bind ref.")
    # Mode B: motion + GLB + rig (build the Puppeteer target from the rig).
    p.add_argument("--glb", help="Target character GLB (mode B: motion + rig).")
    p.add_argument("--rig", help="Puppeteer rig txt (mode B).")
    p.add_argument("--source-anim",
                   help="Source motion FBX/BVH (mode B). Dispatched by extension.")
    p.add_argument("--global-scale", type=float, default=1.0,
                   help="BVH import scale for mode B (reconcile units with the rig).")
    p.add_argument("--left-sign", type=int, choices=(-1, 1), default=None,
                   help="Override the source world-X 'left' sign (labels only).")
    p.add_argument("--output", required=True)
    return p.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    # Mode B: motion + GLB + rig (the "just BVH + GLB" path).
    if args.glb and args.rig and args.source_anim:
        generate_from_motion(args.glb, args.rig, args.source_anim, args.output,
                             global_scale=args.global_scale, left_sign=args.left_sign)
        return

    # Mode A: FBX pair.
    if not (args.puppeteer_fbx and args.mixamo_fbx):
        raise SystemExit(
            "Provide either (--glb --rig --source-anim) for motion-based "
            "generation, or (--puppeteer-fbx --mixamo-fbx) for the FBX pair."
        )
    clear_scene()
    print(f"[1/3] Importing Puppeteer: {args.puppeteer_fbx}")
    pup = import_fbx_armature(args.puppeteer_fbx, "Puppeteer")
    print(f"[2/3] Importing Mixamo:    {args.mixamo_fbx}")
    mix = import_fbx_armature(args.mixamo_fbx, "Mixamo")
    bpy.context.scene.frame_set(int(bpy.context.scene.frame_start))

    print("[3/3] Inferring mapping from topology + geometry...")
    bone_map, chains, src_root, pup_root = build_mapping(mix, pup, args.left_sign)

    print(f"  matched {len(bone_map)} bones across "
          f"{sum(1 for v in chains.values() if v['source'])} chains")
    for k, v in chains.items():
        print(f"    {k:10s} ({len(v['source']):d}): "
              f"{v['source']}  ->  {v['puppeteer']}")

    write_json(args.output, bone_map, chains, src_root, pup_root,
               source_label="Mixamo", origin="FBX topology")
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)
