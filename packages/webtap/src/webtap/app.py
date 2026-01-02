"""Main application entry point for WebTap browser debugger.

PUBLIC API:
  - app: Main ReplKit2 App instance
"""

from dataclasses import dataclass, field

from replkit2 import App

from webtap.client import RPCClient


@dataclass
class _WebTapState:
    """Application state for WebTap browser debugging."""

    client: RPCClient = field(init=False)

    def __post_init__(self):
        """Initialize RPC client after dataclass init."""
        self.client = RPCClient()

    def cleanup(self):
        """Cleanup resources on exit."""
        if hasattr(self, "client") and self.client:
            self.client.close()


app = App(
    "webtap",
    _WebTapState,
    mcp_config={
        "uri_scheme": "webtap",
        "instructions": "Chrome DevTools Protocol debugger",
    },
    typer_config={
        "add_completion": False,
        "help": "WebTap - Chrome DevTools Protocol CLI",
    },
)

from webtap.commands import connection  # noqa: E402, F401
from webtap.commands import navigation  # noqa: E402, F401
from webtap.commands import javascript  # noqa: E402, F401
from webtap.commands import network  # noqa: E402, F401
from webtap.commands import request  # noqa: E402, F401
from webtap.commands import console  # noqa: E402, F401
from webtap.commands import entry  # noqa: E402, F401
from webtap.commands import filters  # noqa: E402, F401
from webtap.commands import fetch  # noqa: E402, F401
from webtap.commands import to_model  # noqa: E402, F401
from webtap.commands import quicktype  # noqa: E402, F401
from webtap.commands import selections  # noqa: E402, F401
from webtap.commands import setup  # noqa: E402, F401
from webtap.commands import launch  # noqa: E402, F401

__all__ = ["app"]
