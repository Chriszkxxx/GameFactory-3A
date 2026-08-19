#!/bin/bash
# Qwen Image Edit + RMBG / Depth Anything local runtime.
# Model weights are downloaded from Hugging Face on first use.

set -e

conda create -n qwen_image python=3.10 -y
conda activate qwen_image

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install diffusers transformers accelerate safetensors huggingface_hub
pip install pillow numpy scipy

echo "Done. Activate the env with: conda activate qwen_image"
echo "Default image model: Qwen/Qwen-Image-Edit-2511"
echo "Default mask model: briaai/RMBG-1.4"
