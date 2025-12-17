"""Daemon-side state with CDP session and services.

PUBLIC API:
  - DaemonState: State container for daemon process
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from webtap.cdp import CDPSession
    from webtap.services import WebTapService


class DaemonState:
    """Daemon-side state with CDP session and services.

    This class is only used in daemon mode (--daemon flag).
    It holds the CDP session and service layer that manage
    browser connections and state.

    Attributes:
        cdp: CDP session for Chrome DevTools Protocol communication
        browser_data: DOM selections and inspection state
        service: WebTapService orchestrator for all operations
        error_state: Current error state dict or None
    """

    cdp: "CDPSession"
    browser_data: Any
    service: "WebTapService"
    error_state: dict[str, Any] | None

    def __init__(self):
        """Initialize daemon state with CDP session and services."""
        from webtap.cdp import CDPSession
        from webtap.services import WebTapService

        self.cdp = CDPSession()
        self.browser_data = None
        self.service = WebTapService(self)
        self.error_state = None

    def cleanup(self):
        """Clean up resources on shutdown."""
        if self.service:
            self.service.disconnect()  # Cleans up DOM, fetch, body services
        if self.cdp:
            self.cdp.cleanup()


__all__ = ["DaemonState"]
