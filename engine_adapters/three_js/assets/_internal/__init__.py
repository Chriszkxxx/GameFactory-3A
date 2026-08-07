"""Private asset implementation for the three.js adapter."""

from .artifacts import ArtifactRecord, ArtifactRegistry
from .inspectors import inspect_source
from .service import AssetService, AssetValidation
from .source_resolver import (
    GeneratedAssetSourceResolver,
    ResolvedAssetSource,
)

__all__ = [
    "ArtifactRecord",
    "ArtifactRegistry",
    "AssetService",
    "AssetValidation",
    "GeneratedAssetSourceResolver",
    "ResolvedAssetSource",
    "inspect_source",
]
