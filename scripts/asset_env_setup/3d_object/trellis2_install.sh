#!/bin/bash
# docs/trellis2_install.sh
# TRELLIS.2 environment setup.
# o-voxel source is already checked in at:
#   models/gen_3d_object/trellis_utils/trellis_2_utils/o_voxel_src/
# So TRELLIS_DIR points there; setup_cu124.sh builds the C++ extensions in-place.

set -e

# Resolve repo root relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TRELLIS_DIR="$REPO_ROOT/models/gen_3d_object/trellis_utils/trellis_2_utils"
EIGEN_DIR="$TRELLIS_DIR/o-voxel/third_party/eigen"

echo "TRELLIS_DIR = $TRELLIS_DIR"

# 1. Create & activate conda env
conda create -n trellis2 python=3.10 -y
conda activate trellis2

# 2. PyTorch (CUDA 12.4)
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
conda install -y -c nvidia cuda-toolkit=12.4

# 3. Eigen (required by o-voxel C++ extension)
git clone https://gitlab.com/libeigen/eigen.git "$EIGEN_DIR"

# 4. Flash-Attention
pip install psutil
pip install flash-attn==2.7.3 --no-build-isolation

# 5. Transformers (pinned version)
pip install transformers==4.57.1

# 6. Build C++ extensions (nvdiffrast, o-voxel, flexgemm, etc.)
#    setup_cu124.sh was copied from the original TRELLIS.2-main repo.
#    If it is not present, copy it from /path/to/TRELLIS.2-main/setup_cu124.sh
cd "$TRELLIS_DIR"
bash setup_cu124.sh --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm

echo "Done. Activate the env with: conda activate trellis2"
