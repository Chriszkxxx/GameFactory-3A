#!/usr/bin/env bash
# Unity-native generated-game wrapper. The JSON job is consumed through the
# public UnityClient; Unity owns the single Editor import/compile/build/play
# lifecycle inside the generated project.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="${A3GAME_PYTHON:-$(command -v python3 || command -v python)}"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" -m engine_adapters.unity3d.cli generate-game "$@"
