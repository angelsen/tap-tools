"""Base classes for termtap screens.

PUBLIC API:
  - TermtapScreen: Base screen with common patterns
"""

from textual.screen import Screen

from ...client import DaemonClient

__all__ = ["TermtapScreen"]


class TermtapScreen(Screen):
    """Base screen with common patterns.

    Screens use container pattern:
    - Background wraps children (animated background with card content)
    - Solid panels (.content-panel) for other screens
    """

    BINDINGS = [("escape", "back", "Back")]

    DEFAULT_CSS = """
    TermtapScreen {
        width: 1fr;
        height: 1fr;
        background: transparent;
    }
    """

    def __init__(self):
        super().__init__()
        self._client = None

    @property
    def client(self) -> DaemonClient:
        """Lazy-initialized daemon client."""
        if self._client is None:
            self._client = DaemonClient(auto_start=False)
        return self._client

    def action_back(self) -> None:
        """Default back action - pop screen."""
        self.app.pop_screen()

    def rpc(self, method: str, params: dict | None = None) -> dict | None:
        """Make RPC call, return result or None on failure."""
        try:
            return self.client.call(method, params)
        except Exception:
            return None
