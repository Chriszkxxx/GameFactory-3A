# Asset environment setup

Use the directory matching the asset task. Each task entry is the canonical
installation path. `cloud_api_install.sh` at this directory root is the shared
implementation used by task-specific cloud API wrappers; do not invoke it in
new agent workflows unless no task-specific wrapper applies.

| Asset task | Setup path | Purpose |
|---|---|---|
| Image / T-pose | `image/cloud_api_install.sh`, `image/qwen_image_install.sh` | Cloud Seedream wrapper and local Qwen Image Edit with RMBG / Depth Anything. |
| 3D object | `3d_object/cloud_api_install.sh`, `3d_object/trellis2_install.sh` | Cloud 3D wrappers and local TRELLIS.2 runtime. |
| 3D scene | `3d_scene/` | Reserved for scene-generation setup; no repository-wide installer is currently required. |
| Motion | `gen_motion/install.sh`, `gen_motion/runtime_env.sh` | Pinned Puppeteer, MoMask, retargeting environments, and selected weights. |
| Audio | `audio/cloud_api_install.sh` | Shared HTTP dependency for cloud audio backends. |
| CG video | `cg_video/cloud_api_install.sh`, `cg_video/minimax_h3_install.sh` | Cloud video wrappers and optional local MiniMax H3/ComfyUI runtime. |

Large checkpoints, cloned third-party sources, and engine/asset installers belong
outside the repository checkout or under `third_party/`; do not commit them.
