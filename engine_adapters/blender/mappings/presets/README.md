# Moved

Bone-map presets for the motion pipeline now live under:

`operators/gen_motion/funcs/retarget_utils/presets/`

The gen_motion retarget path uses that copy. The auto-mapping script here
(`generate_mapping_auto.py`) still works for ad-hoc Blender work, but prefer
`operators.gen_motion.funcs.retarget_utils.mapping_auto` for pipeline tasks.
