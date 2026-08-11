"""Private asset implementation for the three.js adapter."""

from .artifacts import ArtifactRecord, ArtifactRegistry
from .inspectors import inspect_source
from .orientation import (
    RUNTIME_FORWARD_AXIS,
    RUNTIME_UP_AXIS,
    OrientationError,
    analyze_geometry,
    apply_orientation_update,
    default_orientation,
    orientation_from_options,
    runtime_yaw_degrees,
    yaw_degrees_between,
)
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
    "OrientationError",
    "RUNTIME_FORWARD_AXIS",
    "RUNTIME_UP_AXIS",
    "ResolvedAssetSource",
    "analyze_geometry",
    "apply_orientation_update",
    "default_orientation",
    "inspect_source",
    "orientation_from_options",
    "runtime_yaw_degrees",
    "yaw_degrees_between",
]
