# models/

Thin wrappers around individual generation models. **One file per model.**

Each wrapper should expose a uniform interface (e.g., `load()`, `infer()`,
`unload()`) so operators can swap backends without knowing implementation details.

Two contracts apply, both in `agent_skills/develop_harness/`:
`model_require.md` for local-weight models, plus `api_model_require.md` (R9) when
the model is a closed-source cloud API. Shared cloud plumbing (HTTP retry, error
classification, response cache, submit → poll → download) lives in
`models/common/cloud_api.py` — do not re-implement it per provider.

## Implemented wrappers

| Slot | Class | File | Kind | Needs |
|------|-------|------|------|-------|
| `gen_3d_object` | `Trellis2Model` | `gen_3d_object/trellis_2_model.py` | local weights | GPU + the o-voxel extension |
| `gen_3d_object` | `TripoModel` | `gen_3d_object/tripo_model.py` | cloud API | `$TRIPO_API_KEY` + `scripts/installing/cloud_api_install.sh` |
| `gen_3d_object` | `MeshyModel` | `gen_3d_object/meshy_model.py` | cloud API | `$MESHY_API_KEY` + `scripts/installing/cloud_api_install.sh` |
| `gen_cg_video` | `SeedanceModel` | `gen_cg_video/seedance_model.py` | cloud API | `$ARK_API_KEY` + `scripts/installing/cloud_api_install.sh` |
| `gen_image` | `QwenEditModel` | `gen_image/qwen_edit_model.py` | local weights | GPU |
| `gen_motion` | `PuppeteerModel` | `gen_motion/puppeteer_model.py` | external source + local weights | CUDA rigging runtime |
| `gen_motion` | `MoMaskModel` | `gen_motion/momask_model.py` | external source + local weights | CPU or CUDA generation runtime |
| `tools/image_matting` | `RMBGModel`, `DepthAnythingModel` | `tools/image_matting/{rmbg_model.py,depth_anything_model.py}` | local weights | — |

`PuppeteerModel` and `MoMaskModel` run their fixed upstream repositories in
isolated subprocesses. This avoids namespace collisions and releases GPU memory
between the rigging and motion-generation stages. Their repositories, weights,
caches and test assets are external runtime data; only these wrappers and the
reproducible setup scripts belong in Git.

All three `gen_3d_object` backends expose the same
`infer_and_save(image, output_path, seed, decimation_target, texture_size)`, so
`Gen3DObjectOperator` swaps between them without changing (R6). Pick one with
`python pipeline/assets_gen/gen_3d_object/run.py --backend {trellis2,tripo,meshy}`.

| | Tripo | Meshy |
|---|---|---|
| free tier | 2000 credits on sign-up | 100 credits / month |
| formats | GLB (conversion endpoint not wired) | GLB, FBX, OBJ, USDZ, STL |
| text-to-3D | one task | preview + refine (two billed tasks) |
| low poly | `smart_low_poly`, P-series models | `model_type="lowpoly"` |
| face budget | `face_limit` | `target_polycount`, 100-300 000 |

## Sub-modules

| Directory        | Purpose                              | Candidate models |
|------------------|--------------------------------------|------------------|
| `gen_3d_object/` | Single 3D asset generation           | TRELLIS.2, Hunyuan3D-2.1, TripoSG, Step1X-3D, Direct3D-S2, Craftsman3D, Michelangelo, Meshy, Tripo, Rodin, CSM, Luma Genie |
| `gen_3d_scene/`  | Whole-scene / world generation       | Hunyuan-WorldPlay2, FlashWorld, FantasyWorld |
| `gen_motion/`    | Motion generation and rigging models | Puppeteer and MoMask implemented; MDM, MLD, T2M-GPT, MotionGPT are candidates |
| `gen_cg_video/`  | Cinematic / CG video generation      | LTX-2.3, HunyuanVideo, Wan, Mochi, CogVideoX, Open-Sora, Seedance 2, Kling 3, Veo 3, Sora 2, Runway Gen-4, Hailuo, Vidu |
| `gen_audio/`     | Character voice, dialogue, and game sound generation | Future speech, voice, and sound-effect backends |
| `reasoning/`     | LLMs / VLMs used by the pipeline     | Claude, GPT-5.5, GLM, Kimi, DeepSeek, Gemini, Qwen, Grok, Llama, Mistral |
| `tools/`         | Utility models (depth, RMBG, seg.)   | Depth-Anything, RMBG, SAM, etc.       |
| `unified_model/` | Composite / multimodal pipelines     | e.g., end-to-end asset+motion models  |
