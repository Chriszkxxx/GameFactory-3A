"""AAAGame artifact records and registry."""

from .models import ArtifactRecord, build_artifact_records
from .registry import ArtifactRegistry

__all__ = ["ArtifactRecord", "ArtifactRegistry", "build_artifact_records"]
