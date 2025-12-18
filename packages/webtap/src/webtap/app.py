"""Main application entry point for WebTap browser debugger.

PUBLIC API:
  - WebTapState: Application state class with daemon client
  - app: Main ReplKit2 App instance (imported by commands and __init__)
"""

import sys
from dataclasses import dataclass, field

from replkit2 import App

from webtap.client import RPCClient


@dataclass
class WebTapState:
    """Application state for WebTap browser debugging.

    Client-side state that communicates with the daemon via HTTP.
    All CDP operations and data storage happen in the daemon.

    Attributes:
        client: RPCClient for JSON-RPC communication with daemon.
    """

    client: RPCClient = field(init=False)

    def __post_init__(self):
        """Initialize RPC client after dataclass init."""
        self.client = RPCClient()

    def cleanup(self):
        """Cleanup resources on exit."""
        if hasattr(self, "client") and self.client:
            self.client.close()


# Must be created before command imports for decorator registration
app = App(
    "webtap",
    WebTapState,
    mcp_config={
        "uri_scheme": "webtap",
        "instructions": "Chrome DevTools Protocol debugger",
    },
    typer_config={
        "add_completion": False,  # Hide shell completion options
        "help": "WebTap - Chrome DevTools Protocol CLI",
    },
)

# Command imports trigger @app.command decorator registration
if "--cli" in sys.argv:
    # Only import CLI-compatible commands (no dict/list parameters)
    from webtap.commands import setup  # noqa: E402, F401
    from webtap.commands import launch  # noqa: E402, F401
else:
    # Import all commands for REPL/MCP mode
    from webtap.commands import connection  # noqa: E402, F401
    from webtap.commands import navigation  # noqa: E402, F401
    from webtap.commands import javascript  # noqa: E402, F401
    from webtap.commands import network  # noqa: E402, F401
    from webtap.commands import request  # noqa: E402, F401
    from webtap.commands import console  # noqa: E402, F401
    from webtap.commands import filters  # noqa: E402, F401
    from webtap.commands import fetch  # noqa: E402, F401
    from webtap.commands import to_model  # noqa: E402, F401
    from webtap.commands import quicktype  # noqa: E402, F401
    from webtap.commands import selections  # noqa: E402, F401

    # from webtap.commands import server  # noqa: E402, F401  # Removed: daemon-only architecture
    from webtap.commands import setup  # noqa: E402, F401
    from webtap.commands import launch  # noqa: E402, F401


# Entry point is in __init__.py:main() as specified in pyproject.toml


__all__ = ["WebTapState", "app"]
