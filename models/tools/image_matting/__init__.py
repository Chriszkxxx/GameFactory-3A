"""
`models.tools.image_matting` — foreground / background separation models.

These are auxiliary "matting" style models used by generation pipelines
(e.g. `gen_tpose_image`) to isolate a character from its background:

- `RMBGModel`         : direct alpha-mask segmentation (BRIA RMBG-1.4).
- `DepthAnythingModel`: depth estimation, combined with white-bg
                        suppression to derive a foreground mask.

All of them inherit from `BaseToolModel` (see `models/tools/base.py`).
"""

from models.tools.image_matting.depth_anything_model import DepthAnythingModel
from models.tools.image_matting.rmbg_model import RMBGModel

__all__ = ["DepthAnythingModel", "RMBGModel"]
