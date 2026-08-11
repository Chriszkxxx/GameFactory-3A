"""
The file formats each end of a retarget accepts.

Kept in its own module because both sides need it and only one side can import
``bpy``: ``rig_io`` uses these to dispatch a Blender importer, while the host
process uses them to reject a bad path before paying for a Blender start-up.
Importing ``rig_io`` from the host to read a tuple of strings would fail on the
``import bpy`` at the top of it.
"""
from __future__ import annotations


#: Character-mesh containers both Blender and trimesh can read. Two readers is
#: the constraint: the rig's weight table is indexed over trimesh's vertex
#: array while the visible mesh comes from Blender's importer, so a format only
#: qualifies when both agree on vertex order.
SUPPORTED_MESH_SUFFIXES = (".glb", ".gltf", ".obj", ".ply", ".stl", ".fbx")

#: Animation containers the retarget can read as a source clip. Both carry an
#: armature with one action, which is the only thing the world-delta transfer
#: needs from a source.
SUPPORTED_MOTION_SUFFIXES = (".bvh", ".fbx")


__all__ = ["SUPPORTED_MESH_SUFFIXES", "SUPPORTED_MOTION_SUFFIXES"]
