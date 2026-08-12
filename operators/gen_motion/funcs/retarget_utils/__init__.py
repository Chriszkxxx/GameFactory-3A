"""
Blender-side helpers for gen_motion retargeting.

Host-safe (any Python): ``validate_mapping``, ``mapping_presets``, ``formats``.
Needs bpy: ``mapping_auto``, ``world_delta``, ``rig_io``, ``inspect_fbx``.

The host driver is ``../retarget_motion.py`` — it shells out to the bpy modules.
Prefer ``mapping_auto``; pass ``mapping_path`` only for an explicit one-off map.
"""
