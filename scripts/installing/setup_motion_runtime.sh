#!/usr/bin/env bash
set -euo pipefail

# Reproducible Linux setup for AAAGameForge human-motion inference.
# Third-party sources, environments and caches stay outside the Git checkout.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${AAAGF_REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." && pwd)}"

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: bash scripts/installing/setup_motion_runtime.sh [RUNTIME_ROOT]

Create the three Linux motion environments and clone pinned upstream sources.
RUNTIME_ROOT defaults to AAAGF_RUNTIME_ROOT or the XDG user data directory.

Optional environment variables:
  AAAGF_CACHE_ROOT       download/build cache root
  AAAGF_CONDA_BIN        Conda executable when it is not on PATH
  AAAGF_CUDA_ARCH_LIST   explicit CUDA architecture list for extension builds
  MAX_JOBS               parallel extension-build jobs (default: 4)
EOF
  exit 0
fi

RUNTIME_ROOT="${1:-${AAAGF_RUNTIME_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/aaagameforge}}"
CACHE_ROOT="${AAAGF_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/aaagameforge}"
PUPPETEER_COMMIT="1c0f9fc6ad209667a0ec5ceac9b59964938a8b51"
MOMASK_COMMIT="94a6636c9c463b7a9414c3401a6f1b67e6c51824"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer targets Linux. On Windows, run it inside WSL2." >&2
  exit 2
fi

if [[ -n "${AAAGF_CONDA_BIN:-}" ]]; then
  CONDA_BIN="${AAAGF_CONDA_BIN}"
elif [[ -n "${CONDA_EXE:-}" ]]; then
  CONDA_BIN="${CONDA_EXE}"
elif command -v conda >/dev/null 2>&1; then
  CONDA_BIN="conda"
else
  CONDA_BIN=""
fi

export AAAGF_RUNTIME_ROOT="${RUNTIME_ROOT}"
export AAAGF_CACHE_ROOT="${CACHE_ROOT}"
export HF_HOME="${CACHE_ROOT}/huggingface"
export PIP_CACHE_DIR="${CACHE_ROOT}/pip"
export TORCH_HOME="${CACHE_ROOT}/torch"
export CONDA_PKGS_DIRS="${CACHE_ROOT}/conda-pkgs"
export CONDA_CHANNEL_PRIORITY="strict"
export MAX_JOBS="${MAX_JOBS:-4}"
if [[ -n "${AAAGF_CUDA_ARCH_LIST:-}" ]]; then
  export TORCH_CUDA_ARCH_LIST="${AAAGF_CUDA_ARCH_LIST}"
fi

mkdir -p \
  "${RUNTIME_ROOT}/sources" \
  "${RUNTIME_ROOT}/test_assets" \
  "${HF_HOME}" "${PIP_CACHE_DIR}" "${TORCH_HOME}" "${CONDA_PKGS_DIRS}" \
  "${RUNTIME_ROOT}/logs"

if [[ -z "${CONDA_BIN}" ]] || ! "${CONDA_BIN}" --version >/dev/null 2>&1; then
  echo "Conda was not found. Install Miniforge/Conda or set AAAGF_CONDA_BIN." >&2
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
  'export CUDA_HOME="${CONDA_PREFIX}"; python -m pip install flash-attn==2.6.3 --no-build-isolation'
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
Runtime root:     ${RUNTIME_ROOT}
Cache root:       ${CACHE_ROOT}
Puppeteer Python: $("${CONDA_BIN}" run -n aaagf-puppeteer python -c 'import sys; print(sys.executable)')
MoMask Python:    $("${CONDA_BIN}" run -n aaagf-momask python -c 'import sys; print(sys.executable)')
Retarget Python:  $("${CONDA_BIN}" run -n aaagf-retarget-bpy python -c 'import sys; print(sys.executable)')

Next:
  export AAAGF_RUNTIME_ROOT="${RUNTIME_ROOT}"
  export AAAGF_CACHE_ROOT="${CACHE_ROOT}"
  source "${REPO_ROOT}/scripts/installing/motion_runtime_env.sh"
  "${CONDA_BIN}" run -n aaagf-momask python \
    "${REPO_ROOT}/scripts/installing/download_motion_weights.py"
EOF
