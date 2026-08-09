#!/usr/bin/env bash
#
# Stage the curated pack of freely licensed glTF models.
#
# Unlike the other launchers this one is not a wrapper over the adapter
# CLI: downloading external content is not an adapter concern. It writes
# asset task outputs and then imports them through the public
# `ThreeClient.assets` API. See fetch_asset_pack.py for the catalogue.
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
    echo "AAAGameForge requires Python 3." >&2
    exit 127
  fi
fi

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/fetch_asset_pack.py" "$@"
