#!/usr/bin/env bash

# Source before real Linux motion runs:
#   source scripts/asset_env_setup/gen_motion/runtime_env.sh

export A3GF_RUNTIME_ROOT="${A3GF_RUNTIME_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/a3gameforge}"
export A3GF_CACHE_ROOT="${A3GF_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/a3gameforge}"
export HF_HOME="${HF_HOME:-${A3GF_CACHE_ROOT}/huggingface}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-${A3GF_CACHE_ROOT}/pip}"
export TORCH_HOME="${TORCH_HOME:-${A3GF_CACHE_ROOT}/torch}"
export CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-${A3GF_CACHE_ROOT}/conda-pkgs}"

export A3GF_PUPPETEER_MODEL_PATH="${A3GF_PUPPETEER_MODEL_PATH:-${A3GF_RUNTIME_ROOT}/sources/Puppeteer}"
export A3GF_MOMASK_MODEL_PATH="${A3GF_MOMASK_MODEL_PATH:-${A3GF_RUNTIME_ROOT}/sources/momask-codes}"

if [[ -z "${A3GF_PUPPETEER_PYTHON:-}" ]] || \
   [[ -z "${A3GF_MOMASK_PYTHON:-}" ]] || \
   [[ -z "${A3GF_RETARGET_BPY_PYTHON:-}" ]]; then
  _A3GF_CONDA_BIN="${A3GF_CONDA_BIN:-${CONDA_EXE:-$(command -v conda || true)}}"
  if [[ -z "${_A3GF_CONDA_BIN}" ]]; then
    echo "Conda was not found. Set A3GF_CONDA_BIN or all three motion Python variables." >&2
    return 2 2>/dev/null || exit 2
  fi

  _a3gameforge_env_python() {
    "${_A3GF_CONDA_BIN}" run -n "$1" python -c \
      'import sys; print(sys.executable)'
  }
  export A3GF_PUPPETEER_PYTHON="${A3GF_PUPPETEER_PYTHON:-$(_a3gameforge_env_python a3gameforge-puppeteer)}"
  export A3GF_MOMASK_PYTHON="${A3GF_MOMASK_PYTHON:-$(_a3gameforge_env_python a3gameforge-momask)}"
  export A3GF_RETARGET_BPY_PYTHON="${A3GF_RETARGET_BPY_PYTHON:-$(_a3gameforge_env_python a3gameforge-retarget-bpy)}"
  unset -f _a3gameforge_env_python
  unset _A3GF_CONDA_BIN
fi
