"""Main application entry point for WebTap browser debugger.

Provides dual REPL/MCP functionality for Chrome DevTools Protocol interaction.
Built on ReplKit2 framework with CDP-native design for browser debugging and
automation leveraging Chrome's native debugging protocol.
"""

from dataclasses import dataclass, field

from replkit2 import App

from webtap.cdp import CDPSession


@dataclass
class WebTapState:
    """Application state for WebTap browser debugging.

    Maintains CDP session and connection state for browser interaction.

    Attributes:
        cdp: Chrome DevTools Protocol session instance.
    """

    cdp: CDPSession = field(default_factory=CDPSession)


# Must be created before command imports for decorator registration
app = App(
    "webtap",
    WebTapState,
    uri_scheme="webtap",
    fastmcp={
        "description": "Chrome DevTools Protocol debugger",
        "tags": {"browser", "debugging", "chrome", "cdp"},
    },
)


# Command imports trigger @app.command decorator registration
from webtap.commands import connection  # noqa: E402, F401
from webtap.commands import navigation  # noqa: E402, F401
from webtap.commands import execution  # noqa: E402, F401
from webtap.commands import network  # noqa: E402, F401
from webtap.commands import console  # noqa: E402, F401


# Entry point is in __init__.py:main() as specified in pyproject.toml
