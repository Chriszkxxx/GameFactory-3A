#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
export PYTHONPATH="${REPOSITORY_ROOT}:${PYTHONPATH:-}"

PYTHON_BIN="${A3GAME_PYTHON:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "3AGameFactory requires Python 3." >&2
    exit 127
  fi
fi

exec "${PYTHON_BIN}" -m engine_adapters.ue5.cli run "$@"
