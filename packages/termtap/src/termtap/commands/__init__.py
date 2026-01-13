"""Termtap REPL commands with daemon architecture.

Commands are registered directly with ReplKit2 app via decorators.
All imports handled by app.py for command registration.

PUBLIC API:
  - execute: Execute command in tmux pane
  - interrupt: Send interrupt signal to pane
  - ls: List all tmux panes
  - pane: Read single pane with paging
  - panes: Read multiple panes with preview
  - send_keystrokes: Send raw keystrokes to pane
  - debug: Debug daemon state via Python eval
"""

from .debug import debug
from .execute import execute
from .interrupt import interrupt
from .ls import ls
from .pane import pane, panes
from .send_keystrokes import send_keystrokes

__all__ = [
    "debug",
    "execute",
    "interrupt",
    "ls",
    "pane",
    "panes",
    "send_keystrokes",
]
