"""Core execution functionality for termtap - simplified.

Commands now own their execution logic. This module provides
shared state management for streaming.

PUBLIC API:
  - ExecutorState: State container for stream management
"""

from .execute import ExecutorState

__all__ = ["ExecutorState"]
