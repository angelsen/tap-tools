"""Core execution functionality for termtap - pane-first architecture.

Provides command execution with streaming output in specific panes.
CommandResult is now imported from types module for consistency.

PUBLIC API:
  - execute: Execute command in tmux pane with streaming output
  - ExecutorState: State container for stream management
"""

from .execute import execute, ExecutorState
from ..types import CommandResult

__all__ = [
    "execute",
    "ExecutorState", 
    "CommandResult",
]