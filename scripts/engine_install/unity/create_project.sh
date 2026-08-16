#!/usr/bin/env bash
# Thin wrapper for a3game-unity create-project
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PYTHON="${A3GAME_PYTHON:-$(command -v python3 || command -v python)}"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" -m engine_adapters.unity3d.cli create-project "$@"
