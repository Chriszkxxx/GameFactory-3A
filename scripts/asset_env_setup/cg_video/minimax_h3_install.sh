#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
COMFYUI_PATH="${COMFYUI_PATH:-$REPO_ROOT/.models/src/ComfyUI}"
COMFYUI_REF="${COMFYUI_REF:-62b3c94bd45154f6486c7abf1b9efcacee96ea69}"

if [ ! -d "$COMFYUI_PATH/.git" ]; then
    mkdir -p "$(dirname "$COMFYUI_PATH")"
    git clone https://github.com/Comfy-Org/ComfyUI.git "$COMFYUI_PATH"
    git -C "$COMFYUI_PATH" checkout --detach "$COMFYUI_REF"
fi

if [ ! -f "$COMFYUI_PATH/comfy_extras/nodes_minimax_h3.py" ]; then
    echo "MiniMax H3 nodes not found in COMFYUI_PATH=$COMFYUI_PATH" >&2
    exit 1
fi

python -m pip install -r "$COMFYUI_PATH/requirements.txt" huggingface_hub

echo "MiniMax H3 local runtime ready:"
echo "  COMFYUI_PATH=$COMFYUI_PATH"
echo "Default model repository: Comfy-Org/MiniMax-H3"
echo "Weights are downloaded lazily for the selected generation mode."
