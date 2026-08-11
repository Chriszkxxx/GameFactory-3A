"""
Retargeting utilities for ``gen_motion``.

The modules here split along one line that matters more than any other: **which
interpreter can import them**.

``bpy`` is a whole Blender inside a wheel, and the environment that owns it is
not the environment that runs the pipeline. So the host process imports only the
two pure-stdlib modules and shells out to the rest:

===================  =========================  =============================
Module               Runs in                    Purpose
===================  =========================  =============================
``validate_mapping``  any Python                 reject a bad mapping early
``mapping_presets``   any Python                 name the source skeletons we
                                                 know, and identify unknown ones
``mapping_auto``      a ``bpy`` interpreter      derive a mapping from topology
``world_delta``       a ``bpy`` interpreter      retarget, then export FBX
``rig_io``            a ``bpy`` interpreter      Puppeteer ``.txt`` -> armature
``inspect_fbx``       a ``bpy`` interpreter      prove the exported FBX imports
===================  =========================  =============================

``retarget_motion.py`` one level up is the host-side driver that invokes the
``bpy`` modules as ``python -m`` subprocesses; nothing in this package should be
imported by the pipeline directly except the two host-safe modules.

Why the mapping is derived and not written down
-----------------------------------------------
Puppeteer names the joints it predicts ``joint0 … jointN``, and those indices
are a property of the mesh it rigged, not of anatomy — the same word ``joint23``
is the hips on one character and a finger on the next. A checked-in
source-to-target bone map is therefore only ever valid for the one character it
was generated against, which is why ``mapping_auto`` exists and why the presets
in ``presets/`` record the rig they are pinned to. See ``mapping_presets`` for
the distinction the registry draws between a reusable *source skeleton profile*
and a pinned mapping.
"""
