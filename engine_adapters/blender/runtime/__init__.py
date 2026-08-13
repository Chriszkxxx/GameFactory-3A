"""
Blender playable runtime: a live `bpy` session driven by JSON commands.

The rest of `engine_adapters/blender/` is batch work: a file goes in, a
conditioned file comes out, the process exits. This is the other mode — one
long-lived process holding a scene that commands mutate while it runs, so a
world can be walked around before it is committed to a game engine.

`serve.py` is the entry point; everything else is importable on its own.
"""
