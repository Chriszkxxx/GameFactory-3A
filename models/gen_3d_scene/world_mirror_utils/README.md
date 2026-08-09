# world_mirror_utils — vendored HunyuanWorld-Mirror

Network definition for [HunyuanWorld-Mirror](https://github.com/Tencent-Hunyuan/HunyuanWorld-Mirror),
the feed-forward geometry model behind Hunyuan WorldPlay's 3D reconstruction.
Weights: `tencent/HunyuanWorld-Mirror` on HuggingFace.

Copied from `HY-WorldPlay/worldcompass/reward_function/HunyuanWorldMirror/src`.
Copyright (C) 2025 Tencent, released under the TENCENT HUNYUANWORLD-MIRROR
COMMUNITY LICENSE AGREEMENT; see the upstream repository for the full text.

## Local modifications

1. **Import prefix rewritten** — `reward_function.HunyuanWorldMirror.src.*` →
   `models.gen_3d_scene.world_mirror_utils.src.*`, so the tree is a normal
   subpackage and needs no `sys.path` manipulation.

2. **Gaussian-splatting branch removed.** Mesh generation reads only the depth,
   pointmap, normal and camera heads. Gone with it: `models/rasterization.py`,
   `utils/frustum.py`, `utils/sh_utils.py`, `utils/act_gs.py`, the `gs_head` /
   `gs_renderer` construction and forward pass in `models/worldmirror.py`, and
   `prepare_contexts`, which nothing else called. That also drops the `gsplat`
   dependency.

   The published checkpoint still carries 67 `gs_*` tensors, so
   `WorldMirrorModel` loads the state dict non-strictly and asserts that every
   skipped key starts with `gs_`. `WorldMirror.__init__` still accepts
   `enable_gs` because `config.json` sets it, but ignores it.

3. **Unused modules deleted** to keep the dependency surface small:
   `src/utils/` entirely (`geometry.py`, `video_utils.py`, `warnings.py` —
   nothing imported them), plus `render_utils.py` (moviepy), `color_map.py`
   (colorspacious, jaxtyping), `build_pycolmap_recon.py` (pycolmap),
   `gs_effects.py`, `cropping.py`, `save_utils.py`, `inference_utils.py`, and
   `visual_util.py`.

   `visual_util.py` held the upstream depth→mesh code (`create_image_mesh`,
   `convert_predictions_to_glb_scene`). It is deliberately **not** vendored —
   `operators/gen_3d_scene/funcs/points_to_mesh.py` replaces it, because the
   upstream version is what produces the holes described in that file's header.

## Refreshing from upstream

```bash
SRC=/path/to/HunyuanWorldMirror
cp -r "$SRC/src" world_mirror_utils/
find world_mirror_utils -name '*.py' -print0 | xargs -0 perl -pi -e \
  's/reward_function\.HunyuanWorldMirror\.src\./models.gen_3d_scene.world_mirror_utils.src./g'
```

Then re-apply modifications 2 and 3 above.
