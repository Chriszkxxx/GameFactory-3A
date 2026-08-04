#!/bin/bash
# scripts/installing/cloud_api_install.sh
# Environment for the closed-source ("cloud API") model wrappers:
#   models/gen_3d_object/tripo_model.py
#   models/gen_3d_object/meshy_model.py
# via the shared plumbing in models/common/cloud_api.py
#
# These wrappers run anywhere Python runs: no GPU, no weights, no compiled
# extensions. The whole dependency is an HTTP client.
#
# Usage:
#   bash scripts/installing/cloud_api_install.sh          # into the active env
#   bash scripts/installing/cloud_api_install.sh --conda  # create a fresh env

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
echo
echo "Verify without spending credits or touching the network:"
echo "  python test/harness/smoke.py --kind 3d_object --backend tripo"
echo "  python test/test_api_3d_object.py"
echo
echo "Check a balance (free, needs a key):"
echo "  python -c \"from models.gen_3d_object import TripoModel; print(TripoModel().balance())\""
