"""Main service orchestrator for WebTap business logic.

PUBLIC API:
  - WebTapService: Main service orchestrating all domain services
"""

from typing import Any

from webtap.filters import FilterManager
from webtap.services.fetch import FetchService
from webtap.services.network import NetworkService
from webtap.services.console import ConsoleService
from webtap.services.body import BodyService


REQUIRED_DOMAINS = [
    "Page",
    "Network",
    "Runtime",
    "Log",
    "DOMStorage",
]


class WebTapService:
    """Main service orchestrating all WebTap domain services.

    Coordinates CDP session management, domain services, and filter management.
    Shared between REPL commands and API endpoints for consistent state.

    Attributes:
        state: WebTap application state instance.
        cdp: CDP session for browser communication.
        enabled_domains: Set of currently enabled CDP domains.
        filters: Filter manager for event filtering.
        fetch: Fetch interception service.
        network: Network monitoring service.
        console: Console message service.
        body: Response body fetching service.
    """

    def __init__(self, state):
        """Initialize with WebTapState instance.

        Args:
            state: WebTapState instance from app.py
        """
        self.state = state
        self.cdp = state.cdp

        self.enabled_domains: set[str] = set()
        self.filters = FilterManager()

        self.fetch = FetchService()
        self.network = NetworkService()
        self.console = ConsoleService()
        self.body = BodyService()

        self.fetch.cdp = self.cdp
        self.network.cdp = self.cdp
        self.console.cdp = self.cdp
        self.body.cdp = self.cdp

        self.fetch.body_service = self.body

        # Legacy wiring for CDP event handler
        self.cdp.fetch_service = self.fetch

    @property
    def event_count(self) -> int:
        """Total count of all CDP events stored."""
        if not self.cdp or not self.cdp.is_connected:
            return 0
        try:
            result = self.cdp.db.execute("SELECT COUNT(*) FROM events").fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def connect_to_page(self, page_index: int | None = None, page_id: str | None = None) -> dict[str, Any]:
        """Connect to Chrome page and enable required domains.

        Args:
            page_index: Index of page to connect to (for REPL)
            page_id: ID of page to connect to (for extension)
        """
        try:
            self.cdp.connect(page_index=page_index, page_id=page_id)

            failures = self.enable_domains(REQUIRED_DOMAINS)

            if failures:
                self.cdp.disconnect()
                return {"error": f"Failed to enable domains: {failures}"}

            self.filters.load()

            page_info = self.cdp.page_info or {}
            return {"connected": True, "title": page_info.get("title", "Untitled"), "url": page_info.get("url", "")}
        except Exception as e:
            return {"error": str(e)}

    def disconnect(self) -> dict[str, Any]:
        """Disconnect from Chrome."""
        was_connected = self.cdp.is_connected

        if self.fetch.enabled:
            self.fetch.disable()

        self.body.clear_cache()

        self.cdp.disconnect()
        self.enabled_domains.clear()

        return {"disconnected": True, "was_connected": was_connected}

    def enable_domains(self, domains: list[str]) -> dict[str, str]:
        """Enable CDP domains.

        Args:
            domains: List of domain names to enable
        """
        failures = {}
        for domain in domains:
            try:
                self.cdp.execute(f"{domain}.enable")
                self.enabled_domains.add(domain)
            except Exception as e:
                failures[domain] = str(e)
        return failures

    def get_status(self) -> dict[str, Any]:
        """Get current connection and state status."""
        if not self.cdp.is_connected:
            return {
                "connected": False,
                "events": 0,
                "fetch_enabled": self.fetch.enabled,
                "paused_requests": 0,
                "network_requests": 0,
                "console_messages": 0,
                "console_errors": 0,
            }

        page_info = self.cdp.page_info or {}

        return {
            "connected": True,
            "connected_page_id": page_info.get("id"),  # Stable page ID
            "url": page_info.get("url"),
            "title": page_info.get("title"),
            "events": self.event_count,
            "fetch_enabled": self.fetch.enabled,
            "paused_requests": self.fetch.paused_count if self.fetch.enabled else 0,
            "network_requests": self.network.request_count,
            "console_messages": self.console.message_count,
            "console_errors": self.console.error_count,
            "enabled_domains": list(self.enabled_domains),
        }

    def clear_events(self) -> dict[str, Any]:
        """Clear all stored CDP events."""
        self.cdp.clear_events()
        return {"cleared": True, "events": 0}

    def list_pages(self) -> dict[str, Any]:
        """List available Chrome pages."""
        try:
            pages = self.cdp.list_pages()
            connected_id = self.cdp.page_info.get("id") if self.cdp.page_info else None
            for page in pages:
                page["is_connected"] = page.get("id") == connected_id
            return {"pages": pages}
        except Exception as e:
            return {"error": str(e), "pages": []}
