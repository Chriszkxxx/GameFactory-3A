#!/usr/bin/env bash

# Source this file before real Linux motion runs:
#   source scripts/installing/motion_runtime_env.sh

export AAAGF_RUNTIME_ROOT="${AAAGF_RUNTIME_ROOT:-${XDG_DATA_HOME:-${HOME}/.local/share}/aaagameforge}"
export AAAGF_CACHE_ROOT="${AAAGF_CACHE_ROOT:-${XDG_CACHE_HOME:-${HOME}/.cache}/aaagameforge}"
export HF_HOME="${HF_HOME:-${AAAGF_CACHE_ROOT}/huggingface}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-${AAAGF_CACHE_ROOT}/pip}"
export TORCH_HOME="${TORCH_HOME:-${AAAGF_CACHE_ROOT}/torch}"
export CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-${AAAGF_CACHE_ROOT}/conda-pkgs}"

export AAAGF_PUPPETEER_MODEL_PATH="${AAAGF_PUPPETEER_MODEL_PATH:-${AAAGF_RUNTIME_ROOT}/sources/Puppeteer}"
export AAAGF_MOMASK_MODEL_PATH="${AAAGF_MOMASK_MODEL_PATH:-${AAAGF_RUNTIME_ROOT}/sources/momask-codes}"

if [[ -z "${AAAGF_PUPPETEER_PYTHON:-}" ]] || \
   [[ -z "${AAAGF_MOMASK_PYTHON:-}" ]] || \
   [[ -z "${AAAGF_RETARGET_BPY_PYTHON:-}" ]]; then
  if [[ -n "${AAAGF_CONDA_BIN:-}" ]]; then
    _AAAGF_CONDA_BIN="${AAAGF_CONDA_BIN}"
  elif [[ -n "${CONDA_EXE:-}" ]]; then
    _AAAGF_CONDA_BIN="${CONDA_EXE}"
  elif command -v conda >/dev/null 2>&1; then
    _AAAGF_CONDA_BIN="conda"
  else
    echo "Conda was not found. Set AAAGF_CONDA_BIN or the three AAAGF_*_PYTHON variables." >&2
    return 2 2>/dev/null || exit 2
  fi

  _aaagf_env_python() {
    "${_AAAGF_CONDA_BIN}" run -n "$1" python -c \
      'import sys; print(sys.executable)'
  }
  export AAAGF_PUPPETEER_PYTHON="${AAAGF_PUPPETEER_PYTHON:-$(_aaagf_env_python aaagf-puppeteer)}"
  export AAAGF_MOMASK_PYTHON="${AAAGF_MOMASK_PYTHON:-$(_aaagf_env_python aaagf-momask)}"
  export AAAGF_RETARGET_BPY_PYTHON="${AAAGF_RETARGET_BPY_PYTHON:-$(_aaagf_env_python aaagf-retarget-bpy)}"
  unset -f _aaagf_env_python
  unset _AAAGF_CONDA_BIN
fi
