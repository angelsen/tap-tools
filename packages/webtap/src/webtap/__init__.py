"""WebTap - Chrome DevTools Protocol REPL.

Main entry point for WebTap browser debugging tool. Provides both REPL and MCP
functionality for Chrome DevTools Protocol interaction with native CDP event
storage and on-demand querying.

PUBLIC API:
  - app: Main ReplKit2 App instance
  - main: Entry point function for CLI
"""

import sys
import logging

from webtap.app import app
from webtap.api import start_api_server

logger = logging.getLogger(__name__)


def main():
    """Entry point for the WebTap REPL.

    Starts either MCP mode (with --mcp flag) or REPL mode with API server
    for Chrome extension integration. The API server runs in background
    to handle extension requests while REPL provides interactive commands.
    """
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        # Start API server for extension
        _start_api_server_safely()

        # Run REPL
        app.run(title="WebTap - Chrome DevTools Protocol REPL")


def _start_api_server_safely():
    """Start API server with error handling."""
    try:
        start_api_server(app.state)
        logger.info("API server started on http://localhost:8765")
    except Exception as e:
        logger.warning(f"Failed to start API server: {e}")


__all__ = ["app", "main"]
