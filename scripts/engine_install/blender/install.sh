#!/bin/bash
# scripts/engine_install/blender/install.sh
# Sudo-free Blender for engine_adapters/blender/ — the importers, the preview
# renderer, and the game/mechanic pipeline.
#
# A portable Blender tarball plus a conda prefix holding the X11/GL shared
# libraries the host does not ship. Nothing is installed system-wide.
#
# The reasoning, the failure signatures and the GPU notes live in
# scripts/engine_install/blender/README.md. This script is that document executed.
#
# Usage:
#   bash scripts/engine_install/blender/install.sh                   # into $HOME/.aaagf
#   AAAGF_TOOLS_DIR=/big/disk/.aaagf bash scripts/engine_install/blender/install.sh
#   bash scripts/engine_install/blender/install.sh --xvfb            # + virtual display
#
# Re-running is safe: each step skips work that is already done.

set -euo pipefail

BLENDER_VERSION="${BLENDER_VERSION:-4.5.12}"
TOOLS_DIR="${AAAGF_TOOLS_DIR:-$HOME/.aaagf}"
WANT_XVFB=0
[ "${1:-}" == "--xvfb" ] && WANT_XVFB=1

SERIES="${BLENDER_VERSION%.*}"                      # 4.5.12 -> 4.5
TARBALL="blender-${BLENDER_VERSION}-linux-x64.tar.xz"
URL="https://download.blender.org/release/Blender${SERIES}/${TARBALL}"
BLENDER_HOME="$TOOLS_DIR/blender-${BLENDER_VERSION}-linux-x64"
LIB_ENV="$TOOLS_DIR/envs/bl"
XVFB_ENV="$TOOLS_DIR/envs/xvfb"
ENV_SCRIPT="$TOOLS_DIR/blender_env.sh"

command -v conda >/dev/null || { echo "conda not found; it provides the libraries" >&2; exit 1; }

# About 2.5 GB: 361 MB tarball, 1.2 GB extracted, 0.9 GB of libraries. Checked
# up front because the interesting failure is not "no space" — it is a Cycles
# kernel cache that fails to write silently and recompiles on every render.
mkdir -p "$TOOLS_DIR"
FREE_MB=$(df -Pm "$TOOLS_DIR" | awk 'NR==2 {print $4}')
if [ "$FREE_MB" -lt 3000 ]; then
    echo "Only ${FREE_MB} MB free at $TOOLS_DIR; ~2500 MB needed." >&2
    echo "Set AAAGF_TOOLS_DIR to a filesystem with room." >&2
    exit 1
fi

# 1. The application.
if [ -x "$BLENDER_HOME/blender" ]; then
    echo "[1/4] Blender ${BLENDER_VERSION} already at $BLENDER_HOME"
else
    echo "[1/4] Downloading Blender ${BLENDER_VERSION}"
    curl -fL --retry 3 -o "$TOOLS_DIR/$TARBALL" "$URL"
    tar -xf "$TOOLS_DIR/$TARBALL" -C "$TOOLS_DIR"
    rm -f "$TOOLS_DIR/$TARBALL"          # 361 MB of nothing, once extracted
fi

# 2. The libraries. All twelve in one command, because the dynamic loader names
#    only the first missing one — installing what the error asks for turns a
#    single step into seven runs that each reveal the next.
if [ -d "$LIB_ENV/lib" ]; then
    echo "[2/4] Library prefix already at $LIB_ENV"
else
    echo "[2/4] Creating library prefix (a few minutes)"
    conda create -y -p "$LIB_ENV" -c conda-forge \
        xorg-libxi xorg-libxxf86vm xorg-libxfixes xorg-libxrender xorg-libxext \
        xorg-libx11 xorg-libsm xorg-libice libxkbcommon mesalib libglu ffmpeg
fi

# 3. A virtual display, only for --play without a physical one.
if [ "$WANT_XVFB" == "1" ] && [ ! -x "$XVFB_ENV/bin/Xvfb" ]; then
    echo "[3/4] Creating Xvfb prefix"
    conda create -y -p "$XVFB_ENV" -c conda-forge xorg-xvfb-server
else
    echo "[3/4] Xvfb skipped (pass --xvfb to install it)"
fi

# 4. The env script. These are variables rather than wrapper scripts because
#    Blender is invoked directly by the generated launch.sh / play.sh too.
echo "[4/4] Writing $ENV_SCRIPT"
cat > "$ENV_SCRIPT" <<EOF
#!/usr/bin/env bash
# Written by scripts/engine_install/blender/install.sh. Source, do not execute.
#
#   source "$ENV_SCRIPT"
#   "\$BLENDER" --background --factory-startup --python script.py -- --arg
export BLENDER_HOME="$BLENDER_HOME"
export BLENDER="\$BLENDER_HOME/blender"
export AAAGF_BLENDER="\$BLENDER"
# The portable build links against X11/GL libraries this host lacks; they come
# from a conda prefix rather than being installed system-wide.
export LD_LIBRARY_PATH="$LIB_ENV/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
# Cycles caches compiled kernels under XDG_CACHE_HOME. On a full filesystem that
# write fails silently and every render recompiles from scratch.
export XDG_CACHE_HOME="$TOOLS_DIR/cache"
export TMPDIR="$TOOLS_DIR/tmp"
mkdir -p "\$XDG_CACHE_HOME" "\$TMPDIR"
EOF
chmod +x "$ENV_SCRIPT"

# Proves the loader, the libraries and the binary together — the one check that
# fails if any of the three is wrong.
# shellcheck disable=SC1090
source "$ENV_SCRIPT"
echo
"$BLENDER" --version | head -1

cat <<EOF

Done. Every shell that runs Blender needs:

  source $ENV_SCRIPT

Check the GPU backends actually available (listed is not the same as usable):

  "\$BLENDER" -b --factory-startup --python-expr "\\
import bpy; p = bpy.context.preferences.addons['cycles'].preferences; \\
print([d.name for d in p.get_devices_for_type('CUDA')])"

Run a mechanic end to end without rendering (needs
engine_adapters/blender/examples/):

  "\$BLENDER" -b --factory-startup \\
      --python engine_adapters/blender/examples/FPSExample/game.py -- \\
      --out-dir /tmp/aaagf_check --no-render

Assets are optional: with no BLENDER_ASSET_ROOT a run logs one
"[assets] no model at ..." per reference, falls back to primitives, and reports
byte-identical gameplay. Grey boxes are not a broken install.

Why each variable exists, and what each failure looks like:
scripts/engine_install/blender/README.md
EOF
