# models/

Thin wrappers around individual generation models. **One file per model.**

Each wrapper should expose a uniform interface (e.g., `load()`, `infer()`,
`unload()`) so operators can swap backends without knowing implementation details.

## Sub-modules

| Directory        | Purpose                              | Candidate models |
|------------------|--------------------------------------|------------------|
| `gen_3d_object/` | Single 3D asset generation           | TRELLIS.2, Hunyuan3D-2.1, TripoSG, Step1X-3D, Direct3D-S2, Craftsman3D, Michelangelo, Meshy, Tripo, Rodin, CSM, Luma Genie |
| `gen_3d_scene/`  | Whole-scene / world generation       | Hunyuan-WorldPlay2, FlashWorld, FantasyWorld |
| `gen_motion/`    | Text-to-motion                       | MoMask, MDM, MLD, T2M-GPT, MotionGPT |
| `gen_cg_video/`  | Cinematic / CG video generation      | LTX-2.3, HunyuanVideo, Wan, Mochi, CogVideoX, Open-Sora, Seedance 2, Kling 3, Veo 3, Sora 2, Runway Gen-4, Hailuo, Vidu |
| `gen_audio/`     | Character voice, dialogue, and game sound generation | Future speech, voice, and sound-effect backends |
| `retarget/`      | Skeleton motion retargeter           | Keemap-based, IK-based, learning-based |
| `reasoning/`     | LLMs / VLMs used by the pipeline     | Claude, GPT-5.5, GLM, Kimi, DeepSeek, Gemini, Qwen, Grok, Llama, Mistral |
| `tools/`         | Utility models (depth, RMBG, seg.)   | Depth-Anything, RMBG, SAM, etc.       |
| `unified_model/` | Composite / multimodal pipelines     | e.g., end-to-end asset+motion models  |
