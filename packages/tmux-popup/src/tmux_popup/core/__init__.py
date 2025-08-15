"""Core components for tmux-popup.

PUBLIC API:
  - Element: Base class for all UI elements
  - Interactive: Base class for interactive gum elements
  - ShellBuilder: Shell script builder for gum commands
  - Dimension: Type alias for size specifications (int or str)
  - BorderStyle: Type alias for border style literals
  - Align: Type alias for alignment literals
  - TimeoutResult: Sentinel class for timed-out operations
  - CancelledResult: Sentinel class for cancelled operations
"""

from .base import Element, Interactive
from .builder import ShellBuilder
from .types import Dimension, BorderStyle, Align, TimeoutResult, CancelledResult

__all__ = [
    "Element",
    "Interactive",
    "ShellBuilder",
    "Dimension",
    "BorderStyle",
    "Align",
    "TimeoutResult",
    "CancelledResult",
]
