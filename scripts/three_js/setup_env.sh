#!/usr/bin/env bash
#
# Provision the Node toolchain the three.js adapter needs.
#
# The adapter shells out to `node` / `npm` through its private Node
# transport, so the only environment requirement is that a Node 20+
# toolchain is on PATH. This script creates that toolchain as a conda
# environment so it is reproducible on a machine with no system Node.
#
# Usage:
#   scripts/three_js/setup_env.sh                     # create or verify
#   scripts/three_js/setup_env.sh --print-activate    # emit activation help
#   scripts/three_js/setup_env.sh --force             # recreate from scratch
#
# Overrides:
#   A3GAME_CONDA_ROOT       conda installation prefix
#   A3GAME_THREE_CONDA_ENV  environment name (default: threejs)
#   A3GAME_NODE_VERSION     Node major/minor spec (default: 20.*)
set -euo pipefail

ENV_NAME="${A3GAME_THREE_CONDA_ENV:-threejs}"
NODE_VERSION="${A3GAME_NODE_VERSION:-20.*}"
PYTHON_VERSION="${A3GAME_PYTHON_VERSION:-3.11}"
FORCE=0
PRINT_ACTIVATE=0

for argument in "$@"; do
  case "${argument}" in
    --force) FORCE=1 ;;
    --print-activate) PRINT_ACTIVATE=1 ;;
    -h|--help)
      sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: ${argument}" >&2
      exit 2
      ;;
  esac
done

resolve_conda_root() {
  if [[ -n "${A3GAME_CONDA_ROOT:-}" ]]; then
    echo "${A3GAME_CONDA_ROOT}"
    return 0
  fi
  if [[ -n "${CONDA_EXE:-}" && -x "${CONDA_EXE}" ]]; then
    dirname "$(dirname "${CONDA_EXE}")"
    return 0
  fi
  local candidate
  for candidate in \
    "${HOME}/miniconda3" \
    "${HOME}/anaconda3" \
    "/opt/conda"; do
    if [[ -x "${candidate}/bin/conda" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

if ! CONDA_ROOT="$(resolve_conda_root)"; then
  echo "conda was not found. Set A3GAME_CONDA_ROOT to its prefix." >&2
  exit 127
fi

CONDA_SH="${CONDA_ROOT}/etc/profile.d/conda.sh"
if [[ ! -f "${CONDA_SH}" ]]; then
  echo "conda profile script is missing: ${CONDA_SH}" >&2
  exit 127
fi

if [[ "${PRINT_ACTIVATE}" == "1" ]]; then
  cat <<ACTIVATE
# Activate the three.js toolchain in an interactive shell:
source ${CONDA_SH}
conda activate ${ENV_NAME}
ACTIVATE
  exit 0
fi

# shellcheck disable=SC1090
source "${CONDA_SH}"

ENV_PREFIX="${CONDA_ROOT}/envs/${ENV_NAME}"
if [[ "${FORCE}" == "1" && -d "${ENV_PREFIX}" ]]; then
  echo "Removing existing environment: ${ENV_PREFIX}"
  conda env remove -y -n "${ENV_NAME}"
fi

if [[ ! -x "${ENV_PREFIX}/bin/node" ]]; then
  echo "Creating conda environment '${ENV_NAME}' (node ${NODE_VERSION})"
  conda create -y -n "${ENV_NAME}" -c conda-forge \
    "nodejs=${NODE_VERSION}" "python=${PYTHON_VERSION}"
else
  echo "Environment '${ENV_NAME}' already provides node; verifying"
fi

conda activate "${ENV_NAME}"

echo "conda prefix : ${CONDA_PREFIX}"
echo "python: $(python --version 2>&1)"
echo "node         : $(node --version)"
echo "npm          : $(npm --version)"

NODE_MAJOR="$(node --version | sed 's/^v\([0-9]*\).*/\1/')"
if (( NODE_MAJOR < 20 )); then
  echo "three.js adapter requires Node 20 or newer; found v${NODE_MAJOR}" >&2
  exit 1
fi

cat <<DONE

three.js toolchain is ready.

  source ${CONDA_SH}
  conda activate ${ENV_NAME}

Then use the public adapter entry points, for example:

  scripts/three_js/create_project.sh --project-path /path/to/GeneratedGame
  scripts/three_js/run.sh --project /path/to/GeneratedGame/package.json
DONE
