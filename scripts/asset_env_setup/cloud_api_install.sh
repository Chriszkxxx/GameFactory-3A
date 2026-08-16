#!/bin/bash
# Shared implementation for task-specific cloud API installers.
# Environment for the closed-source ("cloud API") model wrappers:
#   models/gen_3d_object/tripo_model.py
#   models/gen_3d_object/meshy_model.py
#   models/gen_audio/seed_audio_model.py
#   models/gen_cg_video/seedance_model.py
#   models/gen_cg_video/minimax_h3_model.py
# via the shared plumbing in models/common/cloud_api.py
#
# These wrappers run anywhere Python runs: no GPU, no weights, no compiled
# extensions. The whole dependency is an HTTP client.
#
# This is the shared implementation. Invoke a task-specific wrapper instead:
#   bash scripts/asset_env_setup/3d_object/cloud_api_install.sh
#   bash scripts/asset_env_setup/audio/cloud_api_install.sh --conda
#   bash scripts/asset_env_setup/cg_video/cloud_api_install.sh

set -e

if [ "$1" == "--conda" ]; then
    conda create -n aaagf_api python=3.10 -y
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate aaagf_api
fi

# The API wrappers themselves.
python -m pip install requests

# The CPU-only development harness (test/harness/smoke.py, the offline contract
# tests). Already present in most envs; listed so a bare env works.
python -m pip install pillow numpy

echo
echo "Done. Set the key for whichever backend you use:"
echo "  export TRIPO_API_KEY=...   # https://platform.tripo3d.ai/api-keys"
echo "  export MESHY_API_KEY=...   # https://www.meshy.ai/api"
echo "  export SEED_AUDIO_API_KEY=...  # POST https://openspeech.bytedance.com/api/v3/tts/create"
echo "  export ARK_API_KEY=...      # https://console.volcengine.com/ark"
echo "  export MINIMAX_API_KEY=...  # https://platform.minimax.io"
echo
echo "Verify without spending credits or touching the network:"
echo "  python test/harness/smoke.py --kind 3d_object --backend tripo"
echo "  python test/test_api_3d_object.py"
echo "  python test/harness/smoke.py --kind audio --backend seed_audio"
echo "  python test/test_api_audio.py"
echo "  python test/harness/smoke.py --kind cg_video --backend seedance"
echo "  python test/harness/smoke.py --kind cg_video --backend minimax-h3"
echo
echo "Check a balance (free, needs a key):"
echo "  python -c \"from models.gen_3d_object import TripoModel; print(TripoModel().balance())\""
