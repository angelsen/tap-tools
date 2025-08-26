"""Main application entry point for termtap terminal pane manager.

Provides dual REPL/MCP functionality for terminal pane management with tmux
integration. Built on ReplKit2 framework with pane-centric design for
process-native terminal operations leveraging OS-level information.
"""

from dataclasses import dataclass, field

from replkit2 import App

DEFAULT_TIMEOUT = 30.0
DEFAULT_LINES_PER_PAGE = 50


@dataclass
class PaneCache:
    """Cache entry for a single pane's output.

    Stores command output with metadata for efficient pagination
    and browsing without re-execution.

    Attributes:
        content: Captured output content from the pane.
        timestamp: Unix timestamp when content was captured.
        lines_per_page: Number of lines to display per page.
        source: Source of the content, either "execute" or "read".
    """

    content: str
    timestamp: float
    lines_per_page: int = 50
    source: str = "read"


@dataclass
class TermTapState:
    """Application state for termtap pane management.

    Includes per-pane cache for command outputs to enable efficient
    pagination and browsing without re-execution.

    Attributes:
        read_cache: Mapping of session_window_pane identifiers to PaneCache entries.
    """

    read_cache: dict[str, PaneCache] = field(default_factory=dict)


# Must be created before command imports for decorator registration
app = App(
    "termtap",
    TermTapState,
    uri_scheme="termtap",
    fastmcp={
        "description": "Terminal pane manager with tmux",
        "tags": {"terminal", "automation", "tmux"},
    },
)


# Command imports trigger @app.command decorator registration
from .commands import execute  # noqa: E402, F401
from .commands import pane  # noqa: E402, F401
from .commands import ls  # noqa: E402, F401
from .commands import interrupt  # noqa: E402, F401
from .commands import send_keys  # noqa: E402, F401
from .commands import track  # noqa: E402, F401
from .commands import run  # noqa: E402, F401


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")
