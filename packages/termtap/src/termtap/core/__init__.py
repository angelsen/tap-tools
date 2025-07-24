"""Core termtap functionality.

PUBLIC API:
  - execute: Execute command in tmux session
  - get_result: Get result of async command
  - ExecutorState: State container for command execution
  - abort_command: Abort a running command
"""

from .execute import execute, get_result, ExecutorState, abort_command

__all__ = [
    "execute",
    "get_result",
    "ExecutorState",
    "abort_command",
]
