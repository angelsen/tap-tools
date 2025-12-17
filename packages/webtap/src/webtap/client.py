"""HTTP client for WebTap daemon communication.

PUBLIC API:
  - DaemonClient: HTTP client wrapper for daemon API
"""

import logging
from typing import Any, Dict, List, Optional

import httpx


logger = logging.getLogger(__name__)


class DaemonClient:
    """HTTP client for WebTap daemon API.

    Provides convenience methods for common daemon operations:
    - Data queries (events, single event)
    - CDP relay (arbitrary CDP commands)
    - Connection management (connect, disconnect, status)
    - Fetch interception (enable, disable, resume, fail)

    Attributes:
        base_url: Base URL of the daemon (default: http://localhost:8765)
    """

    def __init__(self, base_url: str = "http://localhost:8765", timeout: float = 30.0):
        """Initialize daemon client.

        Args:
            base_url: Base URL of the daemon
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self._client = httpx.Client(timeout=timeout)

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make GET request to daemon.

        Args:
            path: API path (e.g., "/status", "/events")
            **kwargs: Additional arguments passed to httpx.get

        Returns:
            Response JSON as dictionary

        Raises:
            httpx.HTTPError: On connection or HTTP error
        """
        try:
            response = self._client.get(f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to daemon at {self.base_url}: {e}")
            raise RuntimeError("Cannot connect to daemon. Is it running? Try 'webtap --daemon' to start it.") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error from daemon: {e}")
            raise

    def post(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make POST request to daemon.

        Args:
            path: API path (e.g., "/connect", "/cdp")
            **kwargs: Additional arguments passed to httpx.post

        Returns:
            Response JSON as dictionary

        Raises:
            httpx.HTTPError: On connection or HTTP error
        """
        try:
            response = self._client.post(f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to daemon at {self.base_url}: {e}")
            raise RuntimeError("Cannot connect to daemon. Is it running? Try 'webtap --daemon' to start it.") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error from daemon: {e}")
            raise

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    # Convenience methods for common operations

    def status(self) -> Dict[str, Any]:
        """Get daemon status.

        Returns:
            Status dictionary with connection state, event count, etc.
        """
        return self.get("/status")

    def cdp(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute CDP command via daemon.

        Args:
            method: CDP method name (e.g., "Runtime.evaluate")
            params: CDP method parameters

        Returns:
            CDP response dictionary
        """
        return self.post("/cdp", json={"method": method, "params": params or {}})

    def pages(self) -> List[Dict[str, Any]]:
        """Get available Chrome pages.

        Returns:
            List of page dictionaries from Chrome's /json endpoint
        """
        result = self.get("/pages")
        return result.get("pages", [])

    def connect(self, page: Optional[int] = None, page_id: Optional[str] = None) -> Dict[str, Any]:
        """Connect to Chrome page.

        Args:
            page: Page index (0-based)
            page_id: Page ID string

        Returns:
            Connection result dictionary
        """
        return self.post("/connect", json={"page": page, "page_id": page_id})

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from current page.

        Returns:
            Disconnect result dictionary
        """
        return self.post("/disconnect")

    def clear(self, events: bool = True, console: bool = False) -> Dict[str, Any]:
        """Clear daemon data stores.

        Args:
            events: Clear CDP events from database
            console: Clear console messages

        Returns:
            Clear result dictionary
        """
        return self.post("/clear", json={"events": events, "console": console})

    def fetch(self, action: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Control fetch interception.

        Args:
            action: Action to perform ("enable", "disable", "status")
            options: Optional action-specific options (e.g., {"response": true})

        Returns:
            Fetch interception result dictionary
        """
        if action in ("enable", "disable"):
            enabled = action == "enable"
            response_stage = (options or {}).get("response", False) if enabled else False
            return self.post("/fetch", json={"enabled": enabled, "response_stage": response_stage})
        elif action == "status":
            # Status is returned via /status endpoint
            return self.status()
        else:
            return {"error": f"Unknown action: {action}"}

    def paused_requests(self) -> List[Dict[str, Any]]:
        """Get list of paused fetch requests.

        Returns:
            List of paused request dictionaries
        """
        result = self.get("/paused")
        return result.get("requests", [])

    def resume_request(
        self, rowid: int, modifications: Optional[Dict[str, Any]] = None, wait: float = 0.5
    ) -> Dict[str, Any]:
        """Resume a paused fetch request with optional modifications.

        Args:
            rowid: Row ID of the paused request
            modifications: Optional request/response modifications
            wait: Wait time for next event in seconds

        Returns:
            Resume result dictionary
        """
        return self.post("/resume", json={"rowid": rowid, "modifications": modifications or {}, "wait": wait})

    def fail_request(self, rowid: int, reason: str = "BlockedByClient") -> Dict[str, Any]:
        """Fail a paused fetch request.

        Args:
            rowid: Row ID of the paused request
            reason: CDP error reason

        Returns:
            Fail result dictionary
        """
        return self.post("/fail", json={"rowid": rowid, "reason": reason})

    def fulfill_request(
        self,
        rowid: int,
        response_code: int = 200,
        response_headers: List[Dict[str, str]] | None = None,
        body: str = "",
    ) -> Dict[str, Any]:
        """Fulfill a paused fetch request with custom response.

        Args:
            rowid: Row ID of the paused request
            response_code: HTTP response code
            response_headers: Response headers as list of {name, value} dicts
            body: Response body string

        Returns:
            Fulfill result dictionary
        """
        return self.post(
            "/fulfill",
            json={
                "rowid": rowid,
                "response_code": response_code,
                "response_headers": response_headers or [],
                "body": body,
            },
        )

    def network(
        self,
        limit: int = 20,
        status: Optional[int] = None,
        method: Optional[str] = None,
        type_filter: Optional[str] = None,
        url: Optional[str] = None,
        apply_groups: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get network requests from HAR summary view.

        Args:
            limit: Maximum results to return
            status: Filter by HTTP status code
            method: Filter by HTTP method
            type_filter: Filter by resource type
            url: Filter by URL pattern (supports * wildcard)
            apply_groups: Apply enabled filter groups

        Returns:
            List of request dictionaries
        """
        params: Dict[str, Any] = {"limit": limit, "apply_groups": apply_groups}
        if status is not None:
            params["status"] = status
        if method:
            params["method"] = method
        if type_filter:
            params["type_filter"] = type_filter
        if url:
            params["url"] = url
        result = self.get("/network", params=params)
        return result.get("requests", [])

    def request_details(self, row_id: int) -> Optional[Dict[str, Any]]:
        """Get HAR entry with nested structure.

        Args:
            row_id: Row ID from network() output

        Returns:
            HAR-structured entry or None if not found
        """
        result = self.get(f"/request/{row_id}")
        return result.get("entry")

    def fetch_body(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Fetch response body by CDP request ID.

        Args:
            request_id: CDP request ID

        Returns:
            Dictionary with {body, base64Encoded} or None
        """
        result = self.get(f"/body/by-request-id/{request_id}")
        if "error" in result:
            return None
        return result

    def console(self, limit: int = 50, level: str | None = None) -> List[Dict[str, Any]]:
        """Get console messages with extracted fields.

        Args:
            limit: Maximum results to return
            level: Optional filter by level (error, warning, log, info)

        Returns:
            List of message dictionaries with {id, level, source, message, timestamp}
        """
        params: Dict[str, Any] = {"limit": limit}
        if level:
            params["level"] = level
        result = self.get("/console", params=params)
        return result.get("messages", [])

    # Navigation convenience methods

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to URL.

        Args:
            url: URL to navigate to

        Returns:
            CDP Page.navigate result
        """
        return self.cdp("Page.navigate", {"url": url})

    def reload_page(self, ignore_cache: bool = False) -> Dict[str, Any]:
        """Reload the current page.

        Args:
            ignore_cache: Force reload ignoring cache

        Returns:
            CDP Page.reload result
        """
        return self.cdp("Page.reload", {"ignoreCache": ignore_cache})

    def get_navigation_history(self) -> Dict[str, Any]:
        """Get navigation history.

        Returns:
            CDP Page.getNavigationHistory result with entries and currentIndex
        """
        return self.cdp("Page.getNavigationHistory", {})

    def navigate_to_history_entry(self, entry_id: int) -> Dict[str, Any]:
        """Navigate to specific history entry.

        Args:
            entry_id: History entry ID from getNavigationHistory

        Returns:
            CDP Page.navigateToHistoryEntry result
        """
        return self.cdp("Page.navigateToHistoryEntry", {"entryId": entry_id})

    # JavaScript convenience method

    def evaluate_js(
        self,
        expression: str,
        await_promise: bool = False,
        return_by_value: bool = True,
    ) -> Dict[str, Any]:
        """Evaluate JavaScript expression.

        Args:
            expression: JavaScript code to evaluate
            await_promise: Wait for promise resolution
            return_by_value: Return value instead of remote object

        Returns:
            CDP Runtime.evaluate result
        """
        return self.cdp(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": return_by_value,
            },
        )

    # Filter group methods

    def filters_status(self) -> Dict[str, Any]:
        """Get all filter groups with enabled status.

        Returns:
            Dict mapping group names to their config and enabled status
        """
        return self.get("/filters/status")

    def filters_add(self, name: str, hide: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new filter group.

        Args:
            name: Group name
            hide: Filter config {"types": [...], "urls": [...]}

        Returns:
            Success status
        """
        return self.post(f"/filters/add/{name}", json={"hide": hide})

    def filters_remove(self, name: str) -> bool:
        """Remove a filter group.

        Args:
            name: Group name to remove

        Returns:
            True if removed, False if not found
        """
        result = self.post(f"/filters/remove/{name}")
        return result.get("removed", False)

    def filters_enable(self, name: str) -> bool:
        """Enable a filter group (in-memory).

        Args:
            name: Group name to enable

        Returns:
            True if enabled, False if not found
        """
        result = self.post(f"/filters/enable/{name}")
        return result.get("enabled", False)

    def filters_disable(self, name: str) -> bool:
        """Disable a filter group (in-memory).

        Args:
            name: Group name to disable

        Returns:
            True if disabled, False if not found
        """
        result = self.post(f"/filters/disable/{name}")
        return result.get("disabled", False)


__all__ = ["DaemonClient"]
