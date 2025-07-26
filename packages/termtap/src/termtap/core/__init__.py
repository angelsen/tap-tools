"""Core termtap functionality.

PUBLIC API:
  - execute: Execute command in tmux session with streaming output
  - ExecutorState: State container for stream management
"""

from .execute import execute, ExecutorState

__all__ = [
    "execute",
    "ExecutorState",
]
