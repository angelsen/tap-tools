"""Fetch interception service for request/response debugging.

PUBLIC API:
  - FetchService: Request/response interception via CDP Fetch domain
  - FetchRules: Declarative rules for fetch interception
"""

import base64
import fnmatch
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Thread pool for handling paused requests.
# Callbacks from WebSocket thread cannot block (would deadlock waiting for
# responses that arrive via the same _on_message handler). Dispatch to pool.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fetch-resume")


@dataclass
class FetchRules:
    """Declarative rules for fetch interception.

    Attributes:
        capture: Whether to capture response bodies before continuing
        block: List of URL patterns to block (fail with BlockedByClient)
        mock: Dict of URL pattern -> response body (or dict with body/status)
    """

    capture: bool = False
    block: list[str] = field(default_factory=list)
    mock: dict[str, str | dict] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Check if no rules are configured."""
        return not self.capture and not self.block and not self.mock

    def to_dict(self) -> dict:
        """Convert to dict for state snapshot."""
        return {"capture": self.capture, "block": self.block, "mock": self.mock}


def _matches_pattern(url: str, pattern: str) -> bool:
    """Match URL against glob pattern.

    Patterns:
        * - matches any characters
        ? - matches single character

    Examples:
        _matches_pattern("https://api.example.com/users", "*api*") -> True
        _matches_pattern("https://tracking.com/pixel", "*tracking*") -> True
    """
    return fnmatch.fnmatch(url, pattern)


class FetchService:
    """Fetch interception with declarative rules.

    Provides request/response interception via CDP Fetch domain.
    When rules are active, Fetch.requestPaused events are handled automatically.

    Attributes:
        enabled: Whether fetch interception is currently enabled
        rules: Current FetchRules for auto-handling
        capture_count: Number of bodies captured this session
        service: WebTapService reference for multi-target operations
    """

    def __init__(self):
        """Initialize fetch service."""
        self._lock = threading.Lock()
        self.enabled = False
        self.rules: FetchRules = FetchRules()
        self._capture_count = 0
        self.service: "Any" = None

    def set_service(self, service: "Any") -> None:
        """Set service reference.

        Args:
            service: WebTapService instance
        """
        self.service = service

    def _trigger_broadcast(self) -> None:
        """Trigger SSE broadcast via service (ensures snapshot update)."""
        if self.service:
            try:
                self.service._trigger_broadcast()
            except Exception as e:
                logger.debug(f"Failed to trigger broadcast: {e}")

    @property
    def capture_count(self) -> int:
        """Number of bodies captured this session."""
        return self._capture_count

    # ============= Auto-Resume Callback =============

    def _on_request_paused(self, event: dict, cdp: Any) -> None:
        """Handle Fetch.requestPaused event - dispatch to thread pool.

        This callback runs in the WebSocket receive thread. We CANNOT call
        cdp.execute() here because it blocks waiting for a response that
        arrives via the same _on_message handler - deadlock!

        Instead, dispatch to thread pool and return immediately.

        Args:
            event: CDP Fetch.requestPaused event
            cdp: CDPSession to execute commands on
        """
        # Dispatch to thread pool - returns immediately, unblocks WebSocket thread
        _executor.submit(self._handle_paused_request, event, cdp)

    def _handle_paused_request(self, event: dict, cdp: Any) -> None:
        """Process paused request in thread pool worker.

        Runs in separate thread so cdp.execute() calls don't deadlock.
        Priority: mock > block > capture > continue

        Args:
            event: CDP Fetch.requestPaused event
            cdp: CDPSession to execute commands on
        """
        params = event.get("params", {})
        request_id = params.get("requestId")
        url = params.get("request", {}).get("url", "")

        if not request_id:
            logger.warning("requestPaused event missing requestId")
            return

        # Check if this is Response stage (has responseStatusCode)
        is_response_stage = params.get("responseStatusCode") is not None

        if not is_response_stage:
            # Request stage - just continue immediately (no body to capture)
            try:
                cdp.execute("Fetch.continueRequest", {"requestId": request_id})
                cdp.decrement_paused_count()
            except Exception as e:
                logger.warning(f"Failed to continue request {request_id}: {e}")
            return

        # Response stage - apply rules

        # Check mock patterns (first match wins)
        for pattern, mock_value in self.rules.mock.items():
            if _matches_pattern(url, pattern):
                self._fulfill_with_mock(cdp, request_id, mock_value, params)
                return

        # Check block patterns
        for pattern in self.rules.block:
            if _matches_pattern(url, pattern):
                self._fail_request(cdp, request_id)
                return

        # Capture body if enabled
        if self.rules.capture:
            self._capture_and_continue(cdp, request_id, params)
        else:
            # Default: continue without capture
            try:
                cdp.execute("Fetch.continueResponse", {"requestId": request_id})
                cdp.decrement_paused_count()
            except Exception as e:
                logger.warning(f"Failed to continue response {request_id}: {e}")

    def _capture_and_continue(self, cdp: Any, request_id: str, params: dict) -> None:
        """Fetch response body while paused and store in DuckDB.

        Args:
            cdp: CDPSession to execute commands on
            request_id: Fetch requestId (for Fetch.* commands)
            params: Original event params (for status code check and networkId)
        """
        status_code = params.get("responseStatusCode", 0)
        # networkId correlates with Network domain - use for storage so HAR view works
        network_id = params.get("networkId", request_id)

        # Skip body capture for redirects (no body available per CDP spec)
        if status_code in (301, 302, 303, 307, 308):
            try:
                cdp.execute("Fetch.continueResponse", {"requestId": request_id})
                cdp.decrement_paused_count()
            except Exception as e:
                logger.warning(f"Failed to continue redirect {request_id}: {e}")
            return

        try:
            result = cdp.execute("Fetch.getResponseBody", {"requestId": request_id}, timeout=5)
            body = result.get("body", "")
            base64_encoded = result.get("base64Encoded", False)
            # Store using networkId so it correlates with HAR view (uses Network.requestId)
            cdp.store_response_body(network_id, body, base64_encoded, {"ok": True, "source": "fetch"})
            with self._lock:
                self._capture_count += 1
        except Exception as e:
            logger.debug(f"Body capture failed for {request_id}: {e}")
            # Store failure metadata using networkId for HAR correlation
            cdp.store_response_body(network_id, "", False, {"ok": False, "error": str(e), "source": "fetch"})
        finally:
            try:
                cdp.execute("Fetch.continueResponse", {"requestId": request_id})
                cdp.decrement_paused_count()
            except Exception as e:
                logger.warning(f"Failed to continue after capture {request_id}: {e}")

    def _fulfill_with_mock(self, cdp: Any, request_id: str, mock_value: str | dict, params: dict) -> None:
        """Fulfill request with mock response.

        Args:
            cdp: CDPSession to execute commands on
            request_id: Fetch requestId (for Fetch.* commands)
            mock_value: String body or dict with body/status
            params: Original event params (for networkId)
        """
        network_id = params.get("networkId", request_id)

        if isinstance(mock_value, str):
            body = mock_value
            status = 200
        else:
            body = mock_value.get("body", "")
            status = mock_value.get("status", 200)

        try:
            body_b64 = base64.b64encode(body.encode()).decode()
            cdp.execute(
                "Fetch.fulfillRequest",
                {
                    "requestId": request_id,
                    "responseCode": status,
                    "body": body_b64,
                    "responseHeaders": [{"name": "Content-Type", "value": "application/json"}],
                },
            )
            cdp.decrement_paused_count()

            # Store mock as captured body for request() inspection (use networkId for HAR)
            cdp.store_response_body(network_id, body_b64, True, {"ok": True, "source": "mock"})
        except Exception as e:
            logger.error(f"Failed to fulfill mock for {request_id}: {e}")

    def _fail_request(self, cdp: Any, request_id: str) -> None:
        """Fail request with BlockedByClient error.

        Args:
            cdp: CDPSession to execute commands on
            request_id: CDP request ID
        """
        try:
            cdp.execute("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})
            cdp.decrement_paused_count()
        except Exception as e:
            logger.error(f"Failed to block request {request_id}: {e}")

    # ============= Enable/Disable =============

    def enable(self, rules: dict | None = None) -> dict[str, Any]:
        """Enable fetch interception with declarative rules.

        Args:
            rules: Dict with capture, block, mock keys. Default: {"capture": True}

        Returns:
            Status dict with enabled state and rules
        """
        with self._lock:
            if not self.service:
                return {"enabled": False, "error": "No service"}

            # Parse rules
            rules = rules or {"capture": True}
            self.rules = FetchRules(
                capture=rules.get("capture", False),
                block=rules.get("block", []),
                mock=rules.get("mock", {}),
            )

            # If rules are empty, just disable
            if self.rules.is_empty():
                return self._disable_internal()

            try:
                # Always use Response stage only (no body capture in Request stage)
                patterns = [{"urlPattern": "*", "requestStage": "Response"}]

                # Enable on all current connections and register callbacks
                for conn in self.service.connections.values():
                    conn.cdp.execute("Fetch.enable", {"patterns": patterns})
                    # Register callback with cdp passed via closure
                    cdp = conn.cdp
                    conn.cdp.register_event_callback(
                        "Fetch.requestPaused", lambda event, cdp=cdp: self._on_request_paused(event, cdp)
                    )

                self.enabled = True
                logger.info(f"Fetch interception enabled with rules: {self.rules.to_dict()}")

                self._trigger_broadcast()
                return {
                    "enabled": True,
                    "rules": self.rules.to_dict(),
                    "capture_count": self._capture_count,
                }

            except Exception as e:
                logger.error(f"Failed to enable fetch: {e}")
                return {"enabled": False, "error": str(e)}

    def _disable_internal(self) -> dict[str, Any]:
        """Internal disable - called from within lock."""
        if not self.enabled:
            return {"enabled": False}

        try:
            # Disable on all connections, unregister callbacks, reset counts
            for conn in self.service.connections.values():
                try:
                    # Unregister callback (can't easily reference the exact lambda,
                    # but clearing events list is safe)
                    conn.cdp._event_callbacks.pop("Fetch.requestPaused", None)
                    conn.cdp.execute("Fetch.disable")
                    conn.cdp._paused_count = 0
                except Exception as e:
                    logger.warning(f"Failed to disable fetch on {conn.target}: {e}")

            self.enabled = False
            self.rules = FetchRules()
            self._capture_count = 0

            logger.info("Fetch interception disabled")
            self._trigger_broadcast()
            return {"enabled": False}

        except Exception as e:
            logger.error(f"Failed to disable fetch: {e}")
            return {"enabled": self.enabled, "error": str(e)}

    def disable(self) -> dict[str, Any]:
        """Disable fetch interception on all connected targets.

        Returns:
            Status dict with disabled state
        """
        with self._lock:
            if not self.service:
                return {"enabled": False, "error": "No service"}

            return self._disable_internal()


__all__ = ["FetchRules", "FetchService"]
