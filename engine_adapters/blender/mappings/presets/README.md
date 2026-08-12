# Moved / removed

Checked-in Mixamo / MoMask → Puppeteer bone-map presets were removed: Puppeteer
joint names are per-mesh, so those maps only fit one character and misled the
default path.

Pipeline retarget uses `mapping_auto` (or an explicit `mapping_path` /
optional drop-in under
`operators/gen_motion/funcs/retarget_utils/presets/`).

Ad-hoc Blender mapping: `generate_mapping_auto.py` here, or
`operators.gen_motion.funcs.retarget_utils.mapping_auto`.
