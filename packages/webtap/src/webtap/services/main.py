"""Main service orchestrator for WebTap business logic."""

from typing import Any

from webtap.filters import FilterManager
from webtap.services.fetch import FetchService
from webtap.services.network import NetworkService
from webtap.services.console import ConsoleService
from webtap.services.dom import DOMService
from webtap.services.state_snapshot import StateSnapshot


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
        dom: DOM inspection and element selection service.
    """

    def __init__(self, state):
        """Initialize with WebTapState instance.

        Args:
            state: WebTapState instance from app.py
        """
        import threading

        self.state = state
        self.cdp = state.cdp
        self._state_lock = threading.RLock()  # Reentrant lock - safe to acquire multiple times by same thread

        self.enabled_domains: set[str] = set()
        self.filters = FilterManager()

        # RPC framework (set by server.py after initialization)
        self.rpc: "Any | None" = None

        self.fetch = FetchService()
        self.network = NetworkService()
        self.console = ConsoleService()
        self.dom = DOMService()

        self.fetch.cdp = self.cdp
        self.network.cdp = self.cdp
        self.network.filters = self.filters
        self.console.cdp = self.cdp
        self.dom.set_cdp(self.cdp)
        self.dom.set_state(self.state)
        self.dom.set_broadcast_callback(self._trigger_broadcast)  # DOM calls back for snapshot updates

        self.fetch.set_broadcast_callback(self._trigger_broadcast)  # Fetch calls back for snapshot updates

        # Legacy wiring for CDP event handler
        self.cdp.fetch_service = self.fetch

        # Register DOM event callbacks
        self.cdp.register_event_callback("Overlay.inspectNodeRequested", self.dom.handle_inspect_node_requested)
        self.cdp.register_event_callback("Page.frameNavigated", self.dom.handle_frame_navigated)

        # Register disconnect callback for unexpected disconnects
        self.cdp.set_disconnect_callback(self._handle_unexpected_disconnect)

        # CDPSession calls back here when CDP events arrive
        self.cdp.set_broadcast_callback(self._trigger_broadcast)

        # Broadcast queue for SSE state updates (set by API server)
        self._broadcast_queue: "Any | None" = None

        # Coalescing flag - prevents duplicate broadcasts during rapid CDP events
        # Service owns coalescing (single source of truth)
        self._broadcast_pending = threading.Event()

        # Immutable state snapshot for thread-safe SSE reads
        # Updated atomically on every state change, read without locks
        self._state_snapshot: StateSnapshot = StateSnapshot.create_empty()

    def set_broadcast_queue(self, queue: "Any") -> None:
        """Set queue for broadcasting state changes.

        Args:
            queue: asyncio.Queue for thread-safe signaling
        """
        self._broadcast_queue = queue

    def _create_snapshot(self) -> StateSnapshot:
        """Create immutable state snapshot from current state.

        MUST be called with self._state_lock held to ensure atomic read.

        Returns:
            Frozen StateSnapshot with current state
        """
        # Connection state (read page_info first to avoid race with disconnect)
        page_info = self.cdp.page_info
        connected = self.cdp.is_connected and page_info is not None
        page_id = page_info.get("id", "") if page_info else ""
        page_title = page_info.get("title", "") if page_info else ""
        page_url = page_info.get("url", "") if page_info else ""

        # Event count
        event_count = self.event_count

        # Fetch state
        fetch_enabled = self.fetch.enabled
        response_stage = self.fetch.enable_response_stage
        paused_count = self.fetch.paused_count if fetch_enabled else 0

        # Filter state (convert to immutable tuples)
        fm = self.filters
        filter_groups = list(fm.groups.keys())
        enabled_filters = tuple(fm.enabled)
        disabled_filters = tuple(name for name in filter_groups if name not in enabled_filters)

        # Browser/DOM state (get_state() is already thread-safe internally)
        browser_state = self.dom.get_state()

        # Error state
        error = self.state.error_state
        error_message = error.get("message") if error else None
        error_timestamp = error.get("timestamp") if error else None

        # Deep copy selections to ensure true immutability
        import copy

        selections = copy.deepcopy(browser_state["selections"])

        return StateSnapshot(
            connected=connected,
            page_id=page_id,
            page_title=page_title,
            page_url=page_url,
            event_count=event_count,
            fetch_enabled=fetch_enabled,
            response_stage=response_stage,
            paused_count=paused_count,
            enabled_filters=enabled_filters,
            disabled_filters=disabled_filters,
            inspect_active=browser_state["inspect_active"],
            selections=selections,  # Deep copy ensures nested dicts are immutable
            prompt=browser_state["prompt"],
            pending_count=browser_state["pending_count"],
            error_message=error_message,
            error_timestamp=error_timestamp,
        )

    def _trigger_broadcast(self) -> None:
        """Trigger SSE broadcast with coalescing (thread-safe).

        Called from:
        - CDPSession (CDP events)
        - DOMService (selections)
        - FetchService (interception state)
        - Service methods (connect, disconnect, clear)

        Coalescing: Only queues signal if none pending. Prevents 1000s of
        signals during rapid CDP events. Flag cleared by API after broadcast.

        Uses atomic check-and-set to prevent race where multiple threads
        queue multiple signals before any sets the flag.
        """
        import logging

        logger = logging.getLogger(__name__)

        # Early exit if no queue (API not started yet)
        if not self._broadcast_queue:
            return

        # Always update snapshot, but coalesce broadcast signals
        with self._state_lock:
            # Update snapshot while holding lock (always, for API responses)
            try:
                self._state_snapshot = self._create_snapshot()
            except (TypeError, AttributeError) as e:
                logger.error(f"Programming error in snapshot creation: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to create state snapshot: {e}", exc_info=True)
                return

            # Skip queue signal if broadcast already pending (coalescing)
            if self._broadcast_pending.is_set():
                return
            self._broadcast_pending.set()

        # Signal broadcast (outside lock - queue.put_nowait is thread-safe)
        try:
            self._broadcast_queue.put_nowait({"type": "state_change"})
        except Exception as e:
            # Clear flag if queue failed so next trigger can try
            self._broadcast_pending.clear()
            logger.warning(f"Failed to queue broadcast: {e}")

    def get_state_snapshot(self) -> StateSnapshot:
        """Get current immutable state snapshot (thread-safe, no locks).

        Returns:
            Current StateSnapshot - immutable, safe to read from any thread
        """
        return self._state_snapshot

    def clear_broadcast_pending(self) -> None:
        """Clear broadcast pending flag (called by API after broadcast).

        Allows next state change to trigger a new broadcast.
        Thread-safe - Event.clear() is atomic.
        """
        self._broadcast_pending.clear()

    @property
    def event_count(self) -> int:
        """Total count of all CDP events stored."""
        if not self.cdp or not self.cdp.is_connected:
            return 0
        try:
            result = self.cdp.query("SELECT COUNT(*) FROM events")
            return result[0][0] if result else 0
        except Exception:
            return 0

    def connect_to_page(self, page_index: int | None = None, page_id: str | None = None) -> dict[str, Any]:
        """Connect to Chrome page and enable required domains.

        Pure domain logic - raises exceptions on failure.
        State machine transitions are handled by RPC handlers.

        Args:
            page_index: Index of page to connect to (for REPL)
            page_id: ID of page to connect to (for extension)

        Returns:
            Connection info dict with 'title' and 'url'

        Raises:
            Exception: On connection or domain enable failure
        """
        # If already connected, disconnect first (enables seamless page switching)
        if self.cdp.is_connected:
            self.disconnect()

        # Reset DOM service for new connection (executor may have been shutdown by previous disconnect)
        self.dom.reset()

        # Clear selections BEFORE connect to handle race with pending disconnect cleanup
        # (disconnect handler runs in background thread, might clear after we connect)
        self.dom.clear_selections()

        self.cdp.connect(page_index=page_index, page_id=page_id)

        failures = self.enable_domains(REQUIRED_DOMAINS)

        if failures:
            self.cdp.disconnect()
            raise RuntimeError(f"Failed to enable domains: {failures}")

        self.filters.load()

        page_info = self.cdp.page_info or {}
        self._trigger_broadcast()
        return {"title": page_info.get("title", "Untitled"), "url": page_info.get("url", "")}

    def disconnect(self) -> None:
        """Disconnect from Chrome and clean up all state.

        Pure domain logic - performs full cleanup.
        State machine transitions are handled by RPC handlers.
        """
        if self.fetch.enabled:
            self.fetch.disable()

        self.dom.clear_selections()
        self.dom.cleanup()  # Shutdown executor properly

        # Clear error state on disconnect
        if self.state.error_state:
            self.state.error_state = None

        self.cdp.disconnect()
        self.enabled_domains.clear()

        self._trigger_broadcast()

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

    def clear_events(self) -> dict[str, Any]:
        """Clear all stored CDP events."""
        self.cdp.clear_events()
        self._trigger_broadcast()
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

    def _handle_unexpected_disconnect(self, code: int, reason: str) -> None:
        """Handle unexpected WebSocket disconnect (tab closed, crashed, etc).

        Called from background thread by CDPSession._on_close.
        Performs service-level cleanup and notifies SSE clients.
        Events are preserved for debugging.

        Args:
            code: WebSocket close code (e.g., 1006 = abnormal closure)
            reason: Human-readable close reason
        """
        import logging
        import time

        logger = logging.getLogger(__name__)

        # Map WebSocket close codes to user-friendly messages
        reason_map = {
            1000: "Page closed normally",
            1001: "Browser tab closed",
            1006: "Connection lost (tab crashed or browser closed)",
            1011: "Chrome internal error",
        }

        # Handle None code (abnormal closure with no code)
        if code is None:
            user_reason = "Connection lost (page closed or crashed)"
        else:
            user_reason = reason_map.get(code, f"Connection closed unexpectedly (code {code})")

        logger.warning(f"Unexpected disconnect: {user_reason}")

        try:
            # Thread-safe state cleanup (called from background thread)
            with self._state_lock:
                # Clean up service state (no CDP calls - connection already gone)
                if self.fetch.enabled:
                    self.fetch.enabled = False  # Direct state update, no CDP disable

                self.dom.clear_selections()

                # Events preserved for debugging - use Clear button to remove explicitly
                # DB thread and field_paths persist for reconnection

                # Set error state with disconnect info
                self.state.error_state = {"message": user_reason, "timestamp": time.time()}

                self.enabled_domains.clear()

            # Cleanup outside lock (safe to call multiple times, has internal protection)
            self.dom.cleanup()  # Shutdown executor

            # Notify SSE clients
            self._trigger_broadcast()

            logger.info("Unexpected disconnect cleanup completed")

        except Exception as e:
            logger.error(f"Error during unexpected disconnect cleanup: {e}")
