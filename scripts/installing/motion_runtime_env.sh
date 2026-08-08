#!/usr/bin/env bash

# Source this file before real WSL motion runs:
#   source scripts/installing/motion_runtime_env.sh

export AAAGF_RUNTIME_ROOT="${AAAGF_RUNTIME_ROOT:-/mnt/e/Research/WorldModel/DCAI/AAAGameForge_runtime}"
export AAAGF_WSL_CACHE_ROOT="${AAAGF_WSL_CACHE_ROOT:-/home/zihao/.cache/aaagf}"
export HF_HOME="${AAAGF_RUNTIME_ROOT}/cache/huggingface"
export PIP_CACHE_DIR="${AAAGF_WSL_CACHE_ROOT}/pip"
export TORCH_HOME="${AAAGF_RUNTIME_ROOT}/cache/torch"
# Conda extracts packages containing symlinks and case-sensitive paths.  Keep
# those working caches on the E:-backed WSL ext4 filesystem instead of /mnt/e
# (DrvFS/NTFS); model weights and download caches remain in RUNTIME_ROOT.
export CONDA_PKGS_DIRS="${AAAGF_WSL_CACHE_ROOT}/conda-pkgs"

export AAAGF_PUPPETEER_MODEL_PATH="${AAAGF_RUNTIME_ROOT}/sources/Puppeteer"
export AAAGF_PUPPETEER_PYTHON="/home/zihao/miniforge3/envs/aaagf-puppeteer/bin/python"
export AAAGF_MOMASK_MODEL_PATH="${AAAGF_RUNTIME_ROOT}/sources/momask-codes"
export AAAGF_MOMASK_PYTHON="/home/zihao/miniforge3/envs/aaagf-momask/bin/python"
export AAAGF_RETARGET_BPY_PYTHON="/home/zihao/miniforge3/envs/aaagf-retarget-bpy/bin/python"
