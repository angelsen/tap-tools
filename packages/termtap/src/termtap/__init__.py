"""Process-native tmux pane manager with MCP support.

Terminal pane manager that auto-detects shell types, works with any tmux pane,
and provides process state detection using syscalls. Built on ReplKit2 for dual
REPL/MCP functionality.

PUBLIC API:
  - app: ReplKit2 application instance with termtap commands
  - main: Entry point for CLI
"""

import sys
from .app import app

__version__ = "0.1.0"
__all__ = ["app", "main"]


def main():
    """Run termtap as REPL or MCP server based on command line arguments.

    Checks for --mcp flag to determine mode:
    - With --mcp: Runs as MCP server for integration
    - Without --mcp: Runs as interactive REPL
    """
    # Ensure handlers.md exists on startup
    from .process.handlers.config import ensure_handlers_file
    ensure_handlers_file()
    
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap - Terminal Pane Manager")
