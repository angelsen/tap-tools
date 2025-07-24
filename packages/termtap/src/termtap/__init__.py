"""Process-native tmux session manager with MCP support.

Terminal session manager that auto-detects shell types, works with any tmux session,
and provides process state detection using syscalls. Built on ReplKit2 for dual
REPL/MCP functionality.

PUBLIC API:
- app: ReplKit2 application instance
"""

from .app import app

__version__ = "0.1.0"
__all__ = ["app"]
