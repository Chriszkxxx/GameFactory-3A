#!/bin/bash
# Install ComfyUI's native MiniMax H3 runtime. Weights remain lazy: the model
# wrapper downloads only the exact files required by the requested Mode.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMFYUI_PATH="${COMFYUI_PATH:-$REPO_ROOT/.models/src/ComfyUI}"
# Verified with ComfyUI 0.31.0. Override when intentionally testing a newer
# native MiniMax H3 revision.
COMFYUI_REF="${COMFYUI_REF:-62b3c94bd45154f6486c7abf1b9efcacee96ea69}"

if [ ! -d "$COMFYUI_PATH/.git" ]; then
    mkdir -p "$(dirname "$COMFYUI_PATH")"
    git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFYUI_PATH"
    git -C "$COMFYUI_PATH" checkout --detach "$COMFYUI_REF"
fi

if [ ! -f "$COMFYUI_PATH/comfy_extras/nodes_minimax_h3.py" ]; then
    echo "The configured ComfyUI checkout has no native MiniMax H3 nodes:" >&2
    echo "  $COMFYUI_PATH" >&2
    echo "Update it to ComfyUI 0.30.0 or newer, or use a fresh COMFYUI_PATH." >&2
    exit 1
fi

python -m pip install -r "$COMFYUI_PATH/requirements.txt"
python -m pip install huggingface_hub

echo
echo "MiniMax H3 local runtime installed:"
echo "  COMFYUI_PATH=$COMFYUI_PATH"
echo
echo "Default model repository: Comfy-Org/MiniMax-H3"
echo "Mode-lazy official files:"
echo "  diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
echo "  diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors (R2V only)"
echo "  text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
echo "  vae/minimax_h3_video_vae_fp16.safetensors"
echo "  vae/minimax_h3_audio_vae_fp32.safetensors"
echo
echo "For optimized NVIDIA INT8 execution, use a PyTorch build with CUDA 13.0+."
