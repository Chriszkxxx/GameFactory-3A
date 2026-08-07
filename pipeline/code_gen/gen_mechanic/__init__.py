"""Generate-Mechanic Pipeline entry points."""

from .artifacts import finalize
from .packet import prepare

__all__ = ["finalize", "prepare"]
