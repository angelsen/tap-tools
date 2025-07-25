"""Core termtap functionality.

PUBLIC API:
  - execute: Execute command in tmux session with streaming output
  - ExecutorState: State container for stream management
  - send_interrupt: Send Ctrl+C to a session
  - send_signal: Send arbitrary signal to process
  - kill_process: Force kill a process
"""

from .execute import execute, ExecutorState
from .control import send_interrupt, send_signal, kill_process

__all__ = [
    "execute",
    "ExecutorState",
    "send_interrupt",
    "send_signal",
    "kill_process",
]
