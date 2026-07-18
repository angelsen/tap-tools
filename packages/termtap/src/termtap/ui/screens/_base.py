"""Base classes for termtap screens.

PUBLIC API:
  - TermtapScreen: Base screen with common patterns
  - ActionScreen: Screen bound to a queue action (pattern learning, pane selection)
"""

from textual.screen import Screen

from ...client import DaemonClient

__all__ = ["TermtapScreen", "ActionScreen"]


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
            self._client = DaemonClient()
        return self._client

    def action_back(self) -> None:
        """Default back action - pop screen."""
        self.app.pop_screen()

    def rpc(self, method: str, params: dict | None = None) -> dict | None:
        """Make RPC call, return result or None on failure."""
        try:
            # 5s bound: this blocks the Textual event loop (sync socket);
            # the 30s default would freeze the UI far too long on a stuck daemon.
            return self.client.call(method, params, timeout=5.0)
        except Exception:
            return None


class ActionScreen(TermtapScreen):
    """Screen bound to a queue action (pattern learning, pane selection)."""

    def __init__(self, action: dict):
        super().__init__()
        self.action = action

    def resolve_action(self, result: dict) -> None:
        """Send resolve RPC and pop screen."""
        if action_id := self.action.get("id"):
            self.rpc("resolve", {"action_id": action_id, "result": result})
        self.app.pop_screen()
