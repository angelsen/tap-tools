"""Core termtap functionality.

PUBLIC API:
- execute: Execute command in tmux session
- get_result: Get result of async command
- ExecutorState: State container for command execution
"""

from .execute import execute, get_result, ExecutorState

__all__ = [
    "execute",
    "get_result",
    "ExecutorState",
]