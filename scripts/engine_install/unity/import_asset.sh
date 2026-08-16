#!/usr/bin/env bash
# Thin wrapper for the public a3game-unity asset commands.
# `import-batch` is a top-level CLI command, so dispatch it before adding the
# default `import-asset` command. This keeps the documented one-Editor batch
# workflow usable from this compatibility wrapper.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PYTHON="${A3GAME_PYTHON:-$(command -v python3 || command -v python)}"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${1:-}" == "import-batch" ]]; then
    shift
    exec "$PYTHON" -m engine_adapters.unity3d.cli import-batch "$@"
fi
exec "$PYTHON" -m engine_adapters.unity3d.cli import-asset "$@"
