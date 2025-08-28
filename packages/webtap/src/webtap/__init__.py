"""WebTap - Chrome DevTools Protocol REPL."""

import sys

from webtap.app import app


def main():
    """Entry point for the WebTap REPL."""
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="WebTap - Chrome DevTools Protocol REPL")


__all__ = ["app", "main"]
