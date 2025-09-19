"""WebTap - Chrome DevTools Protocol REPL.

Main entry point for WebTap browser debugging tool. Provides both REPL and MCP
functionality for Chrome DevTools Protocol interaction with native CDP event
storage and on-demand querying.

PUBLIC API:
  - app: Main ReplKit2 App instance
  - main: Entry point function for CLI
"""

import sys

from webtap.app import app


def main():
    """Entry point for the WebTap REPL.

    Starts in one of three modes:
    - CLI mode (with --cli flag) for command-line interface
    - MCP mode (with --mcp flag) for Model Context Protocol server
    - REPL mode (default) for interactive shell

    The API server for Chrome extension communication must be started
    explicitly using the server('start') command.
    """
    if "--mcp" in sys.argv:
        app.mcp.run()
    elif "--cli" in sys.argv:
        # Remove --cli from argv before passing to Typer
        sys.argv.remove("--cli")
        app.cli()  # Run CLI mode via Typer
    else:
        # Run REPL
        app.run(title="WebTap - Chrome DevTools Protocol REPL")


__all__ = ["app", "main"]
