"""UE backend provider."""

from __future__ import annotations

from .backend import UEAssetBackend


class UEAssetBackendProvider:
    engine = "ue"

    def create(self) -> UEAssetBackend:
        return UEAssetBackend()
