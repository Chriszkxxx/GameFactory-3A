#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export A3GAME_BROWSER_PLAY_DIR="$SCRIPT_DIR"
export A3GAME_BROWSER_ENGINE="${A3GAME_BROWSER_ENGINE:-unity3d}"

REPO_ROOT=${A3GAMEFORGE_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)}
cd "$REPO_ROOT"

echo "Browser Play: http://127.0.0.1:7870/game/?engine=$A3GAME_BROWSER_ENGINE"
exec python -m engine_adapters.browser_serving gateway
