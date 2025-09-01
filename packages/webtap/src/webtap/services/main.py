"""WebTap service layer for shared state and operations.

Provides a clean interface for both REPL commands and API endpoints.
"""

from typing import Any

from webtap.filters import FilterManager
from webtap.services.fetch import FetchService
from webtap.services.network import NetworkService
from webtap.services.console import ConsoleService
from webtap.services.body import BodyService


# Required CDP domains for WebTap functionality
REQUIRED_DOMAINS = [
    "Page",  # Navigation, lifecycle, history
    "Network",  # Request/response monitoring
    "Runtime",  # Console API, JavaScript execution
    "Log",  # Browser logs (errors, warnings)
    "DOMStorage",  # localStorage/sessionStorage events
]


class WebTapService:
    """Service layer managing WebTap state and operations.

    This service is shared between REPL commands and API endpoints,
    providing a single source of truth for state management.
    """

    def __init__(self, state):
        """Initialize with WebTapState instance.

        Args:
            state: WebTapState instance from app.py
        """
        self.state = state
        self.cdp = state.cdp

        # Extension/API state
        self.enabled_domains: set[str] = set()

        # Filter management
        self.filters = FilterManager()

        # Service layers for different CDP domains
        self.fetch = FetchService()
        self.network = NetworkService()
        self.console = ConsoleService()
        self.body = BodyService()

        # Wire up services to CDP session
        self.fetch.cdp = self.cdp
        self.network.cdp = self.cdp
        self.console.cdp = self.cdp
        self.body.cdp = self.cdp

        # Wire up inter-service dependencies
        self.fetch.body_service = self.body

        # Legacy wiring for CDP event handler (still needed for now)
        # TODO: Move event handling to service layer
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

        Returns:
            Dict with connection result or error
        """
        try:
            # Step 1: Connect
            self.cdp.connect(page_index=page_index, page_id=page_id)

            # Step 2: Enable required domains
            failures = self.enable_domains(REQUIRED_DOMAINS)

            if failures:
                self.cdp.disconnect()
                return {"error": f"Failed to enable domains: {failures}"}

            # Step 3: Auto-load filters if available
            self.filters.load()

            # Success
            page_info = self.cdp.page_info or {}
            return {"connected": True, "title": page_info.get("title", "Untitled"), "url": page_info.get("url", "")}
        except Exception as e:
            return {"error": str(e)}

    def disconnect(self) -> dict[str, Any]:
        """Disconnect from Chrome.

        Returns:
            Dict with disconnection status
        """
        was_connected = self.cdp.is_connected

        # Disable fetch if enabled
        if self.fetch.enabled:
            self.fetch.disable()

        # Clear body cache
        self.body.clear_cache()

        self.cdp.disconnect()
        self.enabled_domains.clear()

        return {"disconnected": True, "was_connected": was_connected}

    def enable_domains(self, domains: list[str]) -> dict[str, str]:
        """Enable CDP domains.

        Args:
            domains: List of domain names to enable

        Returns:
            Dict of domain -> error message for failures
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
        """Get current connection and state status.

        Returns:
            Dict with comprehensive status information
        """
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
        """Clear all stored CDP events.

        Returns:
            Dict with clear status
        """
        self.cdp.clear_events()
        return {"cleared": True, "events": 0}

    def list_pages(self) -> dict[str, Any]:
        """List available Chrome pages.

        Returns:
            Dict with pages list or error
        """
        try:
            pages = self.cdp.list_pages()
            # Include connected status for each page
            connected_id = self.cdp.page_info.get("id") if self.cdp.page_info else None
            for page in pages:
                page["is_connected"] = page.get("id") == connected_id
            return {"pages": pages}
        except Exception as e:
            return {"error": str(e), "pages": []}
