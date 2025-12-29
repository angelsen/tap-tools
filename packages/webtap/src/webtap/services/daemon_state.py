"""Daemon-side state with CDP session and services.

PUBLIC API:
  - DaemonState: State container for daemon process
"""

from typing import Any


class DaemonState:
    """Daemon-side state with registered ports and services.

    This class is only used in daemon mode (--daemon flag).
    It holds the service layer that manages browser connections and state.

    Attributes:
        registered_ports: Set of Chrome DevTools Protocol ports available
        browser_data: DOM selections and inspection state
        service: WebTapService orchestrator for all operations
        error_state: Per-target error state dict {target_id: {message, timestamp}}
    """

    def __init__(self):
        """Initialize daemon state with registered ports and services."""
        from webtap.services import WebTapService

        self.registered_ports: set[int] = {9222}
        self.browser_data: dict[str, Any] | None = None
        self.service = WebTapService(self)
        self.error_state: dict[str, dict[str, Any]] = {}

    def cleanup(self):
        """Clean up resources on shutdown."""
        if self.service:
            self.service.disconnect()


__all__ = ["DaemonState"]
