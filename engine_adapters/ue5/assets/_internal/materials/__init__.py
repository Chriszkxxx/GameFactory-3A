"""Material and texture helpers shared by object and scene imports."""

from .pbr import (
    PBR_TEXTURE_CHANNELS,
    SUPPORTED_TEXTURE_SUFFIXES,
    discover_pbr_textures,
    normalize_texture_channel,
)

__all__ = [
    "PBR_TEXTURE_CHANNELS",
    "SUPPORTED_TEXTURE_SUFFIXES",
    "discover_pbr_textures",
    "normalize_texture_channel",
]
