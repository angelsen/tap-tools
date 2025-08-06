"""Process-native tmux pane manager with MCP support.

Entry point for termtap application that can run as either a REPL interface
or MCP server depending on command line arguments.
"""

import sys
import logging
from .app import app

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_LOG_DATEFMT = "%H:%M:%S"

logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, datefmt=_LOG_DATEFMT)


def main():
    """Run termtap as REPL or MCP server based on command line arguments.

    Checks for --mcp flag to determine mode:
    - With --mcp: Runs as MCP server for integration
    - Without --mcp: Runs as interactive REPL
    """
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap - Terminal Pane Manager")


if __name__ == "__main__":
    main()
