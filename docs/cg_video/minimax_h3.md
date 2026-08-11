# MiniMax H3 hybrid backend

`MiniMaxH3Model` is one backend with two runtimes:

- `api`: the official MiniMax asynchronous Hailuo 2.3 API;
- `local`: the official pruned INT8/convrot MiniMax H3 checkpoints executed
  through ComfyUI's native MiniMax H3 nodes.

The backend name remains `minimax-h3`. `runtime=auto` selects API for Hailuo
model aliases, and local execution for an existing directory or Hugging Face
repo id.

Official API documentation:

- https://platform.minimax.io/docs/guides/video-generation
- https://platform.minimax.io/docs/api-reference/video-generation-t2v
- https://platform.minimax.io/docs/api-reference/video-generation-i2v

Local runtime references:

- https://docs.comfy.org/tutorials/video/minimax/minimax-h3
- https://huggingface.co/Comfy-Org/MiniMax-H3
- https://github.com/Comfy-Org/ComfyUI/pull/15224

## Capabilities by runtime

MiniMax-Hailuo-2.3 officially supports:

- `text_to_video`
- `first_frame_to_video`

First/last-frame generation belongs to `MiniMax-Hailuo-02`, while subject
reference generation belongs to `S2V-01`. The API runtime therefore rejects
`first_last_frame_to_video` and `reference_to_video` instead of silently using
a different provider model.

The local MiniMax H3 release supports all four shared modes:

- `text_to_video` → FL2VA partition without keyframes;
- `first_frame_to_video` → FL2VA with the first keyframe;
- `first_last_frame_to_video` → FL2VA with both temporal keyframes;
- `reference_to_video` → the separate Ref2VA partition with ordered images.

The distinction between temporal keyframes and references is preserved.

## Authentication

```bash
bash scripts/installing/cloud_api_install.sh
export MINIMAX_API_KEY="your-key"
```

Credentials are resolved on the first non-cached request. Importing or
constructing the model performs no network access.

## Local pruned INT8 installation

```bash
bash scripts/installing/minimax_h3_install.sh
```

For a fresh checkout the installer uses the verified ComfyUI 0.31.0 revision
`62b3c94bd45154f6486c7abf1b9efcacee96ea69`, which includes the native H3
support and its peak-memory fix. An existing `COMFYUI_PATH` is preserved and
must already contain `comfy_extras/nodes_minimax_h3.py` (ComfyUI 0.30.0+).

The default local model id is `Comfy-Org/MiniMax-H3`. This repository contains
many full-precision and quantized variants, so the wrapper never downloads an
unfiltered snapshot. It supplies an exact Hugging Face `allow_patterns` list
for the requested generation mode.

T2V, I2V and FL2V require exactly:

```text
diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
vae/minimax_h3_video_vae_fp16.safetensors
vae/minimax_h3_audio_vae_fp32.safetensors
```

R2V substitutes the diffusion model with:

```text
diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors
```

The FL2VA and Ref2VA weights are mode-lazy. A first T2V/I2V/FL2V call does not
download Ref2VA; a later R2V call adds Ref2VA to the same Hugging Face cache.
The common T2V/I2V set is about 39.6 GiB, and adding R2V brings it to about
59.1 GiB. `pruned_int8_convrot` describes the diffusion checkpoint; the
official text encoder remains the NVFP4-AWQ file listed above.

Use Hugging Face ids directly:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --backend minimax-h3 \
  --minimax-runtime local \
  --ckpt Comfy-Org/MiniMax-H3 \
  --mode text_to_video \
  --prompt "A knight crosses a rain-soaked neon plaza." \
  --duration-sec 5
```

Or provide local directories without changing the backend:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --backend minimax-h3 \
  --minimax-runtime local \
  --ckpt /models/MiniMax-H3 \
  --mode first_last_frame_to_video \
  --first-frame /data/first.png \
  --last-frame /data/last.png \
  --prompt "The camera completes a slow orbit." \
  --duration-sec 5
```

Accepted local paths include a Hugging Face snapshot root, a directory with the
official component subdirectories, a ComfyUI `models/` directory, or a ComfyUI
source tree containing `models/`. Exact official basenames are also discovered
under a supplied parent directory when they are unique.

The default canvas is 864×480 at the native 24 fps. Duration is converted to
frames and snapped upward to the model's `17k+5` grid. Sampling follows the
official workflow: `UNETLoader(weight_dtype="default")`,
`CLIPLoader(type="minimax", device="default")`, 20 `simple` scheduler steps,
`res_multistep`, joint video/audio decode, then MP4 muxing. Do not force an FP8
loader dtype; doing so would bypass the checkpoint's INT8/convrot metadata.
Optimized NVIDIA INT8 execution requires a PyTorch CUDA 13.0+ build according
to ComfyUI's quantized runtime; GPU VRAM, system RAM and disk requirements
remain substantial.

Before the first GPU run, verify `torch.cuda.is_available()`,
`torch.version.cuda`, and at least 40 GiB of free model-cache space (60 GiB when
R2V will also be tested). The first run is expected to spend time downloading
and loading weights; set `--local-files-only` only after the snapshot is fully
cached or when `--ckpt` points at a complete local tree.

## CLI

Text-to-video:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --backend minimax-h3 \
  --mode text_to_video \
  --prompt "A knight crosses a rain-soaked neon plaza." \
  --duration-sec 6 \
  --resolution 1080P \
  --cache-dir test_data/outputs/_api_cache
```

First-frame image-to-video:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --backend minimax-h3 \
  --mode first_frame_to_video \
  --first-frame /data/first.png \
  --prompt "The character turns toward the camera. [Push in]" \
  --duration-sec 10 \
  --resolution 768P
```

Hailuo 2.3 accepts 6s or 10s at 768P, and 6s at 1080P. It does not expose a
seed parameter; the shared request seed is accepted but recorded as ignored in
`last_call_info`.

The API wrapper performs create task → query status → retrieve file metadata →
download, while sharing the existing retry, error classification and billed
response cache with Seedance.

## Offline validation

```bash
python -m unittest test.test_cg_video_gen -v
python test/harness/smoke.py --kind cg_video --backend minimax-h3
```

Paid live validation is opt-in:

```bash
export MINIMAX_API_KEY="your-key"
export AAAGF_RUN_MINIMAX_LIVE=1
export MINIMAX_LIVE_MODES="text_to_video"
python -m unittest test.test_api_cg_video.TestMiniMaxLive -v
```
