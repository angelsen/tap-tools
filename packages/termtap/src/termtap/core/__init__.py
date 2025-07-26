"""Core execution and control functionality for termtap.

Provides command execution with streaming output and process control operations.
The execute module handles command orchestration while control.py contains
internal process control utilities.

PUBLIC API:
  - execute: Execute command in tmux session with streaming output
  - ExecutorState: State container for stream management
  - CommandResult: Result of command execution (returned by execute)
"""

from .execute import execute, ExecutorState, CommandResult

__all__ = [
    "execute",
    "ExecutorState",
    "CommandResult",
]
