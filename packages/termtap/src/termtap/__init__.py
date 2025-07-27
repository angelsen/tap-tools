"""Process-native tmux pane manager with MCP support.

Terminal pane manager that auto-detects shell types, works with any tmux pane,
and provides process state detection using syscalls. Built on ReplKit2 for dual
REPL/MCP functionality.

PUBLIC API:
  - app: ReplKit2 application instance with termtap commands
"""

from .app import app

__version__ = "0.1.0"
__all__ = ["app"]
