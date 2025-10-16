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
    browser_data: dict | None = None  # Browser element selections with prompt
    error_state: dict | None = None  # Current error: {"message": str, "timestamp": float}

    def __post_init__(self):
        """Initialize service with self reference after dataclass init."""
        self.service = WebTapService(self)

    def cleanup(self):
        """Cleanup resources on exit."""
        # Disconnect through service to ensure full cleanup (clears selections, cache, etc)
        if hasattr(self, "service") and self.service and self.cdp.is_connected:
            self.service.disconnect()

        # Stop DOM service cleanup (executor, callbacks)
        if hasattr(self, "service") and self.service and self.service.dom:
            self.service.dom.cleanup()

        # Stop API server if we own it
        if self.api_thread and self.api_thread.is_alive():
            # Import here to avoid circular dependency
            import webtap.api

            webtap.api._shutdown_requested = True
            # Give server 1.5s to close SSE connections and shutdown gracefully
            self.api_thread.join(timeout=1.5)

        # Shutdown DB thread (this is the only place where DB thread should stop)
        if hasattr(self, "cdp") and self.cdp:
            self.cdp.cleanup()


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
    from webtap.commands import console  # noqa: E402, F401
    from webtap.commands import events  # noqa: E402, F401
    from webtap.commands import filters  # noqa: E402, F401
    from webtap.commands import inspect  # noqa: E402, F401
    from webtap.commands import fetch  # noqa: E402, F401
    from webtap.commands import body  # noqa: E402, F401
    from webtap.commands import to_model  # noqa: E402, F401
    from webtap.commands import quicktype  # noqa: E402, F401
    from webtap.commands import selections  # noqa: E402, F401
    from webtap.commands import server  # noqa: E402, F401
    from webtap.commands import setup  # noqa: E402, F401
    from webtap.commands import launch  # noqa: E402, F401


# Entry point is in __init__.py:main() as specified in pyproject.toml


__all__ = ["WebTapState", "app"]
