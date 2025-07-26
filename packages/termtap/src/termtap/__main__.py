"""Process-native tmux session manager with MCP support.

Entry point for termtap application that can run as either a REPL interface
or MCP server depending on command line arguments.
"""

import sys
import logging
from .app import app

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
)


def main():
    """Run termtap as REPL or MCP server based on command line arguments.

    Checks for --mcp flag to determine mode:
    - With --mcp: Runs as MCP server for integration
    - Without --mcp: Runs as interactive REPL
    """
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap - Terminal Session Manager")


if __name__ == "__main__":
    main()
