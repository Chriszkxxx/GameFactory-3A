"""
pipeline/common/

Shared, task-agnostic helpers for every pipeline runner and operator.

`paths` is the single source of truth for input / output locations — never
hand-build an output path in a `run.py`, an `eval.py` or an operator.
"""
from pipeline.common import paths  # noqa: F401

__all__ = ["paths"]
