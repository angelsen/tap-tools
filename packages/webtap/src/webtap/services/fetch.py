"""Fetch interception service for request/response debugging.

PUBLIC API:
  - FetchService: Request/response interception via CDP Fetch domain
  - TargetRules: Per-target block/mock rules
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
class TargetRules:
    """Per-target block/mock rules.

    Attributes:
        block: List of URL patterns to block (fail with BlockedByClient)
        mock: Dict of URL pattern -> response body (or dict with body/status)
    """

    block: list[str] = field(default_factory=list)
    mock: dict[str, str | dict] = field(default_factory=dict)


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
    Capture is enabled by default on connect. Per-target rules for block/mock.

    Attributes:
        capture_enabled: Global flag - capture on by default
        capture_count: Number of bodies captured this session
        service: WebTapService reference for multi-target operations
    """

    def __init__(self):
        """Initialize fetch service."""
        self._lock = threading.Lock()
        self.capture_enabled = True  # Global, default ON
        self._capture_count = 0
        self._target_rules: dict[str, TargetRules] = {}  # Per-target
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

    def _on_request_paused(self, event: dict, cdp: Any, target: str) -> None:
        """Handle Fetch.requestPaused event - dispatch to thread pool.

        This callback runs in the WebSocket receive thread. We CANNOT call
        cdp.execute() here because it blocks waiting for a response that
        arrives via the same _on_message handler - deadlock!

        Instead, dispatch to thread pool and return immediately.

        Args:
            event: CDP Fetch.requestPaused event
            cdp: CDPSession to execute commands on
            target: Target ID for per-target rule lookup
        """
        # Dispatch to thread pool - returns immediately, unblocks WebSocket thread
        _executor.submit(self._handle_paused_request, event, cdp, target)

    def _handle_paused_request(self, event: dict, cdp: Any, target: str) -> None:
        """Process paused request in thread pool worker.

        Runs in separate thread so cdp.execute() calls don't deadlock.
        Priority: mock > block > capture > continue

        Args:
            event: CDP Fetch.requestPaused event
            cdp: CDPSession to execute commands on
            target: Target ID for per-target rule lookup
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

        # Response stage - apply target-specific rules first, then global capture

        # Get rules for this target (if any)
        rules = self._target_rules.get(target)

        if rules:
            # Check mock patterns (target-specific, first match wins)
            for pattern, mock_value in rules.mock.items():
                if _matches_pattern(url, pattern):
                    self._fulfill_with_mock(cdp, request_id, mock_value, params)
                    return

            # Check block patterns (target-specific)
            for pattern in rules.block:
                if _matches_pattern(url, pattern):
                    self._fail_request(cdp, request_id)
                    return

        # Capture body if globally enabled
        if self.capture_enabled:
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

    # ============= Lifecycle Methods =============

    def enable_on_target(self, target: str, cdp: Any) -> None:
        """Enable fetch capture on a newly connected target.

        Called from connect_to_page(). Only enables if capture_enabled.

        Args:
            target: Target ID for this connection
            cdp: CDPSession to enable Fetch on
        """
        if not self.capture_enabled:
            return

        try:
            patterns = [{"urlPattern": "*", "requestStage": "Response"}]
            cdp.execute("Fetch.enable", {"patterns": patterns})
            cdp.register_event_callback(
                "Fetch.requestPaused",
                lambda event, cdp=cdp, target=target: self._on_request_paused(event, cdp, target),
            )
            logger.debug(f"Fetch capture enabled on {target}")
        except Exception as e:
            logger.warning(f"Failed to enable fetch on {target}: {e}")

    def cleanup_target(self, target: str, cdp: Any | None = None) -> None:
        """Clean up fetch state for a disconnected target.

        Called from disconnect_target() and _handle_unexpected_disconnect().

        Args:
            target: Target ID to clean up
            cdp: CDPSession to disable Fetch on (None if already dead)
        """
        with self._lock:
            self._target_rules.pop(target, None)

        if cdp:
            try:
                cdp._event_callbacks.pop("Fetch.requestPaused", None)
                cdp._paused_count = 0
                cdp.execute("Fetch.disable")
            except Exception:
                pass  # CDP may already be dead

        logger.debug(f"Fetch cleanup completed for {target}")

    def set_capture(self, enabled: bool) -> dict:
        """Toggle global capture on/off.

        Args:
            enabled: Whether to enable capture globally

        Returns:
            Current status dict
        """
        with self._lock:
            if enabled == self.capture_enabled:
                return self.get_status()

            self.capture_enabled = enabled

            if not self.service:
                return self.get_status()

            # Enable/disable on all current connections
            for conn in self.service.connections.values():
                try:
                    if enabled:
                        self.enable_on_target(conn.target, conn.cdp)
                    else:
                        conn.cdp._event_callbacks.pop("Fetch.requestPaused", None)
                        conn.cdp.execute("Fetch.disable")
                except Exception:
                    pass

            self._trigger_broadcast()
            return self.get_status()

    def set_rules(self, target: str, block: list[str] | None = None, mock: dict | None = None) -> dict:
        """Set block/mock rules for a specific target.

        Args:
            target: Target ID to set rules for
            block: List of URL patterns to block (None to keep existing)
            mock: Dict of URL pattern -> response body (None to keep existing)

        Returns:
            Current status dict
        """
        with self._lock:
            if block is None and mock is None:
                # Clear rules for target
                self._target_rules.pop(target, None)
            else:
                self._target_rules[target] = TargetRules(
                    block=block or [],
                    mock=mock or {},
                )
            self._trigger_broadcast()
            return self.get_status()

    def get_status(self) -> dict:
        """Get current fetch status.

        Returns:
            Status dict with capture state and per-target rules
        """
        return {
            "capture": self.capture_enabled,
            "capture_count": self._capture_count,
            "rules": {target: {"block": r.block, "mock": r.mock} for target, r in self._target_rules.items()},
        }


__all__ = ["TargetRules", "FetchService"]
