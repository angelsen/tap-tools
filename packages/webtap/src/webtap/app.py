"""Main application entry point for WebTap browser debugger.

PUBLIC API:
  - WebTapState: Application state class with CDP session and service
  - app: Main ReplKit2 App instance (imported by commands and __init__)
"""

import sys
import threading
from dataclasses import dataclass, field

from replkit2 import App

from webtap.cdp import CDPSession
from webtap.services import WebTapService


@dataclass
class WebTapState:
    """Application state for WebTap browser debugging.

    Maintains CDP session and connection state for browser interaction.
    All data is stored in DuckDB via the CDP session - no caching needed.

    Attributes:
        cdp: Chrome DevTools Protocol session instance.
        service: WebTapService orchestrating all domain services.
        api_thread: Thread running the FastAPI server (if this instance owns the port).
    """

    cdp: CDPSession = field(default_factory=CDPSession)
    service: WebTapService = field(init=False)
    api_thread: threading.Thread | None = None

    def __post_init__(self):
        """Initialize service with self reference after dataclass init."""
        self.service = WebTapService(self)

    def cleanup(self):
        """Cleanup resources on exit."""
        # Disconnect CDP if connected
        if self.cdp.is_connected:
            self.cdp.disconnect()

        # Stop API server if we own it
        if self.api_thread and self.api_thread.is_alive():
            # Import here to avoid circular dependency
            import webtap.api

            webtap.api._shutdown_requested = True
            # Wait up to 1 second for graceful shutdown
            self.api_thread.join(timeout=1.0)


# Must be created before command imports for decorator registration
app = App(
    "webtap",
    WebTapState,
    uri_scheme="webtap",
    fastmcp={
        "description": "Chrome DevTools Protocol debugger",
        "tags": {"browser", "debugging", "chrome", "cdp"},
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
    from webtap.commands import console  # noqa: E402, F401
    from webtap.commands import events  # noqa: E402, F401
    from webtap.commands import filters  # noqa: E402, F401
    from webtap.commands import inspect  # noqa: E402, F401
    from webtap.commands import fetch  # noqa: E402, F401
    from webtap.commands import body  # noqa: E402, F401
    from webtap.commands import setup  # noqa: E402, F401
    from webtap.commands import launch  # noqa: E402, F401


# Entry point is in __init__.py:main() as specified in pyproject.toml


__all__ = ["WebTapState", "app"]
