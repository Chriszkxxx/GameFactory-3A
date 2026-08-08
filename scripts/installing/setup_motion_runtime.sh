#!/usr/bin/env bash
set -euo pipefail

# Reproducible WSL setup for AAAGameForge human-motion inference.
# Third-party sources, environments and caches stay outside the Git checkout.

RUNTIME_ROOT="${1:-/mnt/e/Research/WorldModel/DCAI/AAAGameForge_runtime}"
REPO_ROOT="${AAAGF_REPO_ROOT:-/mnt/e/Research/WorldModel/DCAI/AAAGameForge}"
CONDA_BIN="${AAAGF_CONDA_BIN:-/home/zihao/miniforge3/bin/conda}"
PUPPETEER_COMMIT="1c0f9fc6ad209667a0ec5ceac9b59964938a8b51"
MOMASK_COMMIT="94a6636c9c463b7a9414c3401a6f1b67e6c51824"

export AAAGF_WSL_CACHE_ROOT="${AAAGF_WSL_CACHE_ROOT:-/home/zihao/.cache/aaagf}"
export HF_HOME="${RUNTIME_ROOT}/cache/huggingface"
export PIP_CACHE_DIR="${AAAGF_WSL_CACHE_ROOT}/pip"
export TORCH_HOME="${RUNTIME_ROOT}/cache/torch"
export CONDA_PKGS_DIRS="${AAAGF_WSL_CACHE_ROOT}/conda-pkgs"
export CONDA_CHANNEL_PRIORITY="strict"

mkdir -p \
  "${RUNTIME_ROOT}/sources" \
  "${RUNTIME_ROOT}/test_assets" \
  "${HF_HOME}" "${PIP_CACHE_DIR}" "${TORCH_HOME}" "${CONDA_PKGS_DIRS}" \
  "${RUNTIME_ROOT}/logs"

if [[ ! -x "${CONDA_BIN}" ]]; then
  echo "Miniforge is missing: ${CONDA_BIN}" >&2
  echo "Install it inside the E:-backed WSL distro before running this script." >&2
  exit 2
fi

clone_at_commit() {
  local url="$1"
  local destination="$2"
  local commit="$3"
  if [[ ! -d "${destination}/.git" ]]; then
    git clone "${url}" "${destination}"
  fi
  git -C "${destination}" fetch origin "${commit}"
  git -C "${destination}" checkout --detach "${commit}"
}

clone_at_commit \
  https://github.com/Seed3D/Puppeteer.git \
  "${RUNTIME_ROOT}/sources/Puppeteer" \
  "${PUPPETEER_COMMIT}"
git -C "${RUNTIME_ROOT}/sources/Puppeteer" submodule update --init --recursive --force

clone_at_commit \
  https://github.com/EricGuo5513/momask-codes.git \
  "${RUNTIME_ROOT}/sources/momask-codes" \
  "${MOMASK_COMMIT}"

create_env() {
  local name="$1"
  local environment_file="$2"
  if ! "${CONDA_BIN}" env list | awk '{print $1}' | grep -Fxq "${name}"; then
    "${CONDA_BIN}" env create -f "${environment_file}"
  fi
}

create_env \
  aaagf-puppeteer \
  "${REPO_ROOT}/scripts/installing/puppeteer_environment.yml"
create_env \
  aaagf-momask \
  "${REPO_ROOT}/scripts/installing/momask_environment.yml"
create_env \
  aaagf-retarget-bpy \
  "${REPO_ROOT}/scripts/installing/retarget_environment.yml"

"${CONDA_BIN}" install -n aaagf-retarget-bpy -y -c conda-forge \
  xorg-libsm xorg-libxext xorg-libxrender

"${CONDA_BIN}" install -n aaagf-puppeteer -y --override-channels \
  -c nvidia/label/cuda-11.8.0 -c conda-forge \
  "cuda-nvcc=11.8.89" \
  "cuda-cudart-dev=11.8.89" "cuda-cccl=11.8.89" \
  "cuda-driver-dev=11.8.89" "cuda-nvrtc-dev=11.8.89" \
  "gcc_linux-64=11" "gxx_linux-64=11" \
  "libopengl" "numpy=1.26.4"

"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  torch==2.1.1 torchvision==0.16.1 torchaudio==2.1.1 \
  --index-url https://download.pytorch.org/whl/cu118
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  "cython==0.29.36"
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  "tetgen==0.5.2" --no-build-isolation
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  -r "${RUNTIME_ROOT}/sources/Puppeteer/requirements.txt"
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  "numpy==1.26.4"
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  "setuptools==69.5.1" "wheel==0.43.0"
"${CONDA_BIN}" run -n aaagf-puppeteer bash -lc \
  'export CUDA_HOME="${CONDA_PREFIX}" MAX_JOBS=4 TORCH_CUDA_ARCH_LIST=8.9; python -m pip install flash-attn==2.6.3 --no-build-isolation'
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  torch-scatter -f https://data.pyg.org/whl/torch-2.1.1+cu118.html
"${CONDA_BIN}" run -n aaagf-puppeteer python -m pip install \
  --no-index --no-cache-dir pytorch3d \
  -f https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu118_pyt211/download.html

"${CONDA_BIN}" run -n aaagf-momask python -m pip install \
  torch==2.1.1 torchvision==0.16.1 torchaudio==2.1.1 \
  --index-url https://download.pytorch.org/whl/cu118
"${CONDA_BIN}" run -n aaagf-momask python -m pip install \
  "setuptools==69.5.1" "wheel==0.43.0"
"${CONDA_BIN}" run -n aaagf-momask python -m pip install \
  "chumpy==0.70" --no-build-isolation
"${CONDA_BIN}" run -n aaagf-momask python -m pip install \
  "numpy==1.23.5" "einops==0.6.1" "ffmpy==0.3.1" "ftfy==6.1.1" \
  "gdown==4.7.1" "Pillow>=9.2,<11" "PyYAML>=6" scipy scikit-learn \
  scikit-image "matplotlib>=3.6,<3.8" tqdm trimesh \
  "vector-quantize-pytorch==1.6.30" \
  smplx huggingface_hub "requests>=2.32,<3" "urllib3>=2.2,<3" \
  "certifi>=2024"
"${CONDA_BIN}" run -n aaagf-momask python -m pip install \
  "git+https://github.com/openai/CLIP.git"

MICHELANGELO_LINK="${RUNTIME_ROOT}/sources/Puppeteer/skinning/third_partys/Michelangelo"
if [[ ! -e "${MICHELANGELO_LINK}" ]]; then
  ln -s ../../skeleton/third_partys/Michelangelo "${MICHELANGELO_LINK}"
fi

cat <<EOF
Motion runtime environments are ready.
Puppeteer Python: /home/zihao/miniforge3/envs/aaagf-puppeteer/bin/python
MoMask Python:    /home/zihao/miniforge3/envs/aaagf-momask/bin/python
Retarget Python:  /home/zihao/miniforge3/envs/aaagf-retarget-bpy/bin/python
Next: run scripts/installing/download_motion_weights.py from aaagf-momask.
EOF
