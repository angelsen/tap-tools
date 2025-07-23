"""Core termtap functionality."""

from .watcher import wait_for_silence, wait_with_patterns
from .execute import execute, execute_async, get_result, ExecutorState
from .command import prepare_command, needs_bash_wrapper

__all__ = [
    "wait_for_silence",
    "wait_with_patterns", 
    "execute",
    "execute_async",
    "get_result",
    "ExecutorState",
    "prepare_command",
    "needs_bash_wrapper",
]