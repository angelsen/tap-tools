"""WebTap - Chrome DevTools Protocol REPL."""

import sys
import logging

from webtap.app import app
from webtap.api import start_api_server

logger = logging.getLogger(__name__)


def main():
    """Entry point for the WebTap REPL."""
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        # Start API server for extension
        try:
            start_api_server(app.state)
            logger.info("API server started on http://localhost:8765")
        except Exception as e:
            logger.warning(f"Failed to start API server: {e}")

        # Run REPL
        app.run(title="WebTap - Chrome DevTools Protocol REPL")


__all__ = ["app", "main"]
