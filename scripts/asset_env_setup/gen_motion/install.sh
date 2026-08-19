#!/usr/bin/env bash
set -euo pipefail

# Linux setup for A3GameForge human-motion inference. Third-party sources,
# environments, weights, and caches stay outside the repository checkout.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PUPPETEER_ENV="a3gameforge-puppeteer"
MOMASK_ENV="a3gameforge-momask"
RETARGET_ENV="a3gameforge-retarget-bpy"
PUPPETEER_COMMIT="1c0f9fc6ad209667a0ec5ceac9b59964938a8b51"
MOMASK_COMMIT="94a6636c9c463b7a9414c3401a6f1b67e6c51824"

usage() {
  cat <<'EOF'
Usage: bash scripts/asset_env_setup/gen_motion/install.sh [--skip-weights]

Install pinned Puppeteer, MoMask, and Blender-retarget runtimes on Linux.
Selected model weights are downloaded unless --skip-weights is specified.

Optional environment variables:
  A3GF_RUNTIME_ROOT   sources and weights directory
  A3GF_CACHE_ROOT     download and build cache directory
  A3GF_CONDA_BIN      Conda executable when it is not on PATH
  A3GF_CUDA_ARCH_LIST CUDA architecture used to build extensions
  MAX_JOBS                   extension build jobs (default: 4)
EOF
}

DOWNLOAD_WEIGHTS=1
case "${1:-}" in
  "") ;;
  --skip-weights) DOWNLOAD_WEIGHTS=0 ;;
  -h|--help) usage; exit 0 ;;
  *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo "Only one option is supported." >&2; exit 2; }

[[ "$(uname -s)" == "Linux" ]] || {
  echo "This installer targets Linux. Windows users can run it in WSL2." >&2
  exit 2
}

RUNTIME_ROOT="${A3GF_RUNTIME_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/a3gameforge}"
CACHE_ROOT="${A3GF_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/a3gameforge}"
CONDA_BIN="${A3GF_CONDA_BIN:-${CONDA_EXE:-$(command -v conda || true)}}"

[[ -n "${CONDA_BIN}" ]] && "${CONDA_BIN}" --version >/dev/null 2>&1 || {
  echo "Conda was not found. Install Miniforge or set A3GF_CONDA_BIN." >&2
  exit 2
}
command -v git >/dev/null 2>&1 || {
  echo "Git is required to clone Puppeteer and MoMask." >&2
  exit 2
}

export A3GF_RUNTIME_ROOT="${RUNTIME_ROOT}"
export A3GF_CACHE_ROOT="${CACHE_ROOT}"
export HF_HOME="${CACHE_ROOT}/huggingface"
export PIP_CACHE_DIR="${CACHE_ROOT}/pip"
export TORCH_HOME="${CACHE_ROOT}/torch"
export CONDA_PKGS_DIRS="${CACHE_ROOT}/conda-pkgs"
export CONDA_CHANNEL_PRIORITY="strict"
export MAX_JOBS="${MAX_JOBS:-4}"
[[ -z "${A3GF_CUDA_ARCH_LIST:-}" ]] || \
  export TORCH_CUDA_ARCH_LIST="${A3GF_CUDA_ARCH_LIST}"

mkdir -p "${RUNTIME_ROOT}/sources" "${RUNTIME_ROOT}/test_assets" \
  "${RUNTIME_ROOT}/logs" "${HF_HOME}" "${PIP_CACHE_DIR}" \
  "${TORCH_HOME}" "${CONDA_PKGS_DIRS}"

clone_pinned() {
  local url="$1" destination="$2" commit="$3"
  if [[ -d "${destination}/.git" ]] && \
     [[ "$(git -C "${destination}" rev-parse HEAD 2>/dev/null || true)" == "${commit}" ]]; then
    echo "Using pinned source already present: ${destination}"
    return
  fi
  [[ -d "${destination}/.git" ]] || git clone "${url}" "${destination}"
  git -C "${destination}" fetch origin "${commit}"
  git -C "${destination}" checkout --detach "${commit}"
}

ensure_env() {
  local name="$1" python_version="$2"
  if ! "${CONDA_BIN}" env list | awk '{print $1}' | grep -Fxq "${name}"; then
    "${CONDA_BIN}" create -n "${name}" -y -c conda-forge \
      "python=${python_version}" pip
  fi
}

pip_install() {
  local environment="$1"
  shift
  "${CONDA_BIN}" run -n "${environment}" python -m pip install "$@"
}

clone_pinned https://github.com/Seed3D/Puppeteer.git \
  "${RUNTIME_ROOT}/sources/Puppeteer" "${PUPPETEER_COMMIT}"
git -C "${RUNTIME_ROOT}/sources/Puppeteer" \
  submodule update --init --recursive --force
clone_pinned https://github.com/EricGuo5513/momask-codes.git \
  "${RUNTIME_ROOT}/sources/momask-codes" "${MOMASK_COMMIT}"

ensure_env "${PUPPETEER_ENV}" 3.10.13
ensure_env "${MOMASK_ENV}" 3.10
ensure_env "${RETARGET_ENV}" 3.11

"${CONDA_BIN}" install -n "${PUPPETEER_ENV}" -y --override-channels \
  -c nvidia/label/cuda-11.8.0 -c conda-forge \
  "python=3.10.13" pip cmake ninja "gcc_linux-64=11" "gxx_linux-64=11" \
  "cuda-nvcc=11.8.89" "cuda-cudart-dev=11.8.89" \
  "cuda-nvrtc-dev=11.8.89" "cuda-cccl=11.8.89" \
  "cuda-driver-dev=11.8.89" libopengl "numpy=1.26.4"
"${CONDA_BIN}" install -n "${MOMASK_ENV}" -y -c conda-forge \
  "python=3.10" pip ffmpeg "numpy=1.23.5"
"${CONDA_BIN}" install -n "${RETARGET_ENV}" -y -c conda-forge \
  "python=3.11" pip xorg-libsm xorg-libxext xorg-libxrender xorg-libxi \
  libxkbcommon.so.0

pip_install "${PUPPETEER_ENV}" \
  torch==2.1.1 torchvision==0.16.1 torchaudio==2.1.1 \
  --index-url https://download.pytorch.org/whl/cu118
pip_install "${PUPPETEER_ENV}" "cython==0.29.36"
pip_install "${PUPPETEER_ENV}" "tetgen==0.5.2" --no-build-isolation
pip_install "${PUPPETEER_ENV}" \
  -r "${RUNTIME_ROOT}/sources/Puppeteer/requirements.txt"
pip_install "${PUPPETEER_ENV}" \
  "numpy==1.26.4" "setuptools==69.5.1" "wheel==0.43.0"
"${CONDA_BIN}" run -n "${PUPPETEER_ENV}" bash -lc \
  'export CUDA_HOME="${CONDA_PREFIX}"; python -m pip install flash-attn==2.6.3 --no-build-isolation'
pip_install "${PUPPETEER_ENV}" torch-scatter \
  -f https://data.pyg.org/whl/torch-2.1.1+cu118.html
pip_install "${PUPPETEER_ENV}" --no-index --no-cache-dir pytorch3d \
  -f https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/py310_cu118_pyt211/download.html

pip_install "${MOMASK_ENV}" \
  torch==2.1.1 torchvision==0.16.1 torchaudio==2.1.1 \
  --index-url https://download.pytorch.org/whl/cu118
pip_install "${MOMASK_ENV}" "setuptools==69.5.1" "wheel==0.43.0"
pip_install "${MOMASK_ENV}" "chumpy==0.70" --no-build-isolation
pip_install "${MOMASK_ENV}" \
  "numpy==1.23.5" "einops==0.6.1" "ffmpy==0.3.1" "ftfy==6.1.1" \
  "gdown==4.7.1" "Pillow>=9.2,<11" "PyYAML>=6" scipy scikit-learn \
  scikit-image "matplotlib>=3.6,<3.8" tqdm trimesh \
  "vector-quantize-pytorch==1.6.30" smplx huggingface_hub \
  "requests>=2.32,<3" "urllib3>=2.2,<3" "certifi>=2024"
pip_install "${MOMASK_ENV}" "git+https://github.com/openai/CLIP.git"

pip_install "${RETARGET_ENV}" "bpy==4.2.0" "numpy<2" "trimesh>=4.2"

MICHELANGELO="${RUNTIME_ROOT}/sources/Puppeteer/skinning/third_partys/Michelangelo"
[[ -e "${MICHELANGELO}" ]] || \
  ln -s ../../skeleton/third_partys/Michelangelo "${MICHELANGELO}"

if [[ "${DOWNLOAD_WEIGHTS}" -eq 1 ]]; then
  "${CONDA_BIN}" run -n "${MOMASK_ENV}" python \
    "${SCRIPT_DIR}/download_weights.py"
fi

cat <<EOF
Motion environments are ready under ${RUNTIME_ROOT}.

Before running the real pipeline:
  export A3GF_RUNTIME_ROOT="${RUNTIME_ROOT}"
  export A3GF_CACHE_ROOT="${CACHE_ROOT}"
  source "${SCRIPT_DIR}/runtime_env.sh"
EOF

if [[ "${DOWNLOAD_WEIGHTS}" -eq 0 ]]; then
  echo "Download weights later with:"
  echo "  ${CONDA_BIN} run -n ${MOMASK_ENV} python ${SCRIPT_DIR}/download_weights.py"
fi
