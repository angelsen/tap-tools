"""Main service orchestrator for WebTap business logic."""

from typing import Any
from dataclasses import dataclass
import time

from webtap.filters import FilterManager
from webtap.notices import NoticeManager
from webtap.services.fetch import FetchService
from webtap.services.network import NetworkService
from webtap.services.console import ConsoleService
from webtap.services.dom import DOMService
from webtap.services.state_snapshot import StateSnapshot


@dataclass
class ActiveConnection:
    """Tracks an active CDP connection."""

    target: str
    cdp: "Any"  # CDPSession
    page_info: dict
    connected_at: float


_REQUIRED_DOMAINS = [
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
        self.cdp = state.cdp  # Primary CDP session (for backward compatibility)
        self._state_lock = threading.RLock()  # Reentrant lock - safe to acquire multiple times by same thread

        # Multi-target connection tracking
        self.connections: dict[str, ActiveConnection] = {}  # keyed by target string

        self.enabled_domains: set[str] = set()
        self.filters = FilterManager()
        self.notices = NoticeManager()

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
        import copy

        # Connection state - any active connections
        connected = len(self.connections) > 0

        # Primary connection info (for backward compatibility)
        page_info = self.cdp.page_info if self.cdp.is_connected else None
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

        # Multi-target state
        active_targets = tuple(fm.get_targets())
        connections = tuple(
            {"target": conn.target, "title": conn.page_info.get("title", ""), "url": conn.page_info.get("url", "")}
            for conn in self.connections.values()
        )

        # Browser/DOM state (get_state() is already thread-safe internally)
        browser_state = self.dom.get_state()

        # Error state
        error = self.state.error_state
        error_message = error.get("message") if error else None
        error_timestamp = error.get("timestamp") if error else None

        # Deep copy selections to ensure true immutability
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
            active_targets=active_targets,
            connections=connections,
            inspect_active=browser_state["inspect_active"],
            selections=selections,  # Deep copy ensures nested dicts are immutable
            prompt=browser_state["prompt"],
            pending_count=browser_state["pending_count"],
            error_message=error_message,
            error_timestamp=error_timestamp,
            notices=self.notices.get_all(),
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

    def get_connection(self, target: str) -> ActiveConnection | None:
        """Get active connection by target ID.

        Args:
            target: Target ID in format "{port}:{short-id}"

        Returns:
            ActiveConnection if exists, None otherwise
        """
        return self.connections.get(target)

    def connect_to_page(
        self,
        page_index: int | None = None,
        page_id: str | None = None,
        chrome_port: int | None = None,
        target: str | None = None,
    ) -> dict[str, Any]:
        """Connect to Chrome page and enable required domains.

        Now supports multiple simultaneous connections. Does NOT auto-disconnect.

        Args:
            page_index: Index of page to connect to (for REPL)
            page_id: ID of page to connect to (for extension)
            chrome_port: Chrome debug port to connect to (default: 9222)
            target: Target ID to connect to (overrides other params if provided)

        Returns:
            Connection info dict with 'title', 'url', 'target'

        Raises:
            Exception: On connection or domain enable failure
        """
        from webtap.targets import make_target, resolve_target

        # Resolve target from different input methods
        if target:
            # Target provided directly - parse it
            from webtap.targets import parse_target

            port, short_id = parse_target(target)
            # Get pages and resolve to full page
            pages_data = self.list_pages(chrome_port=port)
            target_page = resolve_target(target, pages_data["pages"])
            if not target_page:
                raise ValueError(f"Target '{target}' not found")
            page_id = target_page["id"]
            chrome_port = port
        else:
            # Use port-based resolution
            chrome_port = chrome_port or 9222

        # Check if already connected to this target
        if target:
            existing = self.get_connection(target)
            if existing:
                return {
                    "title": existing.page_info.get("title", "Untitled"),
                    "url": existing.page_info.get("url", ""),
                    "target": existing.target,
                    "already_connected": True,
                }

        # Get the CDP session for this port
        target_cdp = self._get_or_create_session(chrome_port)

        # Connect to the page
        target_cdp.connect(page_index=page_index, page_id=page_id)

        # Enable required domains
        failures = {}
        for domain in _REQUIRED_DOMAINS:
            try:
                target_cdp.execute(f"{domain}.enable")
            except Exception as e:
                failures[domain] = str(e)

        if failures:
            target_cdp.disconnect()
            raise RuntimeError(f"Failed to enable domains: {failures}")

        # Get page info and create target ID
        page_info = target_cdp.page_info or {}
        full_page_id = page_info.get("id", "")
        target_id = make_target(chrome_port, full_page_id)

        # Set target on CDPSession for event tagging
        target_cdp.target = target_id

        # Store connection
        with self._state_lock:
            self.connections[target_id] = ActiveConnection(
                target=target_id, cdp=target_cdp, page_info=page_info, connected_at=time.time()
            )

        # Register callbacks for this session
        target_cdp.set_disconnect_callback(
            lambda code, reason: self._handle_unexpected_disconnect(target_id, code, reason)
        )
        target_cdp.set_broadcast_callback(self._trigger_broadcast)

        # If this is the first connection, wire it as primary for backward compatibility
        if len(self.connections) == 1:
            self.cdp = target_cdp
            self.fetch.cdp = self.cdp
            self.network.cdp = self.cdp
            self.console.cdp = self.cdp
            self.dom.set_cdp(self.cdp)
            self.dom.reset()
            self.dom.clear_selections()
            self.cdp.register_event_callback("Overlay.inspectNodeRequested", self.dom.handle_inspect_node_requested)
            self.cdp.register_event_callback("Page.frameNavigated", self.dom.handle_frame_navigated)

        self.filters.load()
        self._trigger_broadcast()

        return {
            "title": page_info.get("title", "Untitled"),
            "url": page_info.get("url", ""),
            "target": target_id,
        }

    def disconnect_target(self, target: str) -> None:
        """Disconnect specific target.

        Args:
            target: Target ID to disconnect
        """
        conn = self.get_connection(target)
        if not conn:
            return

        # Disconnect CDP session
        conn.cdp.disconnect()

        # Remove from connections
        with self._state_lock:
            self.connections.pop(target, None)

        # If this was the primary connection, clear services
        if self.cdp == conn.cdp:
            self.cdp = self.state.cdp  # Fallback to state's primary session
            if self.fetch.enabled:
                self.fetch.disable()
            self.dom.clear_selections()
            self.dom.cleanup()
            self.enabled_domains.clear()

        self._trigger_broadcast()

    def disconnect(self) -> None:
        """Disconnect all targets and clean up all state.

        Pure domain logic - performs full cleanup.
        State machine transitions are handled by RPC handlers.
        """
        # Disconnect all connections
        targets_to_disconnect = list(self.connections.keys())
        for target in targets_to_disconnect:
            self.disconnect_target(target)

        # Clean up services
        if self.fetch.enabled:
            self.fetch.disable()

        self.dom.clear_selections()
        self.dom.cleanup()

        # Clear error state on disconnect
        if self.state.error_state:
            self.state.error_state = None

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

    def list_pages(self, chrome_port: int | None = None) -> dict[str, Any]:
        """List available Chrome pages with target IDs.

        Args:
            chrome_port: Specific port to query. If None, queries default ports.

        Returns:
            Dict with 'pages' list. Each page includes 'target', 'connected' fields.
        """
        from webtap.targets import make_target

        all_pages = []

        # Query specific port or discover from state's sessions
        if chrome_port:
            ports_to_query = [chrome_port]
        elif hasattr(self.state, "cdp_sessions"):
            ports_to_query = list(self.state.cdp_sessions.keys())
        else:
            ports_to_query = [9222]  # Default

        for port in ports_to_query:
            try:
                # Get CDP session for this port (create if needed)
                cdp_session = self._get_or_create_session(port)
                pages = cdp_session.list_pages()

                # Add metadata to each page
                for page in pages:
                    page_id = page.get("id", "")
                    target_id = make_target(port, page_id)

                    page["target"] = target_id
                    page["chrome_port"] = port
                    page["connected"] = target_id in self.connections
                    all_pages.append(page)

            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to list pages from port {port}: {e}")
                # Continue with other ports

        return {"pages": all_pages}

    def _get_or_create_session(self, port: int) -> "Any":
        """Get or create CDPSession for given port.

        Args:
            port: Chrome debug port

        Returns:
            CDPSession instance for the port
        """
        from webtap.cdp import CDPSession

        # Use daemon state's session dict if available
        if hasattr(self.state, "cdp_sessions"):
            if port not in self.state.cdp_sessions:
                self.state.cdp_sessions[port] = CDPSession(port=port)
            return self.state.cdp_sessions[port]

        # Fallback: return primary session (for testing or non-daemon contexts)
        return self.cdp

    def _handle_unexpected_disconnect(self, target: str, code: int, reason: str) -> None:
        """Handle unexpected WebSocket disconnect for a specific target.

        Called from background thread by CDPSession._on_close.
        Performs service-level cleanup and notifies SSE clients.
        Events are preserved for debugging.

        Args:
            target: Target ID that disconnected
            code: WebSocket close code (e.g., 1006 = abnormal closure)
            reason: Human-readable close reason
        """
        import logging

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

        logger.warning(f"Unexpected disconnect on {target}: {user_reason}")

        try:
            # Thread-safe state cleanup (called from background thread)
            with self._state_lock:
                # Remove connection from tracking
                conn = self.connections.pop(target, None)
                if not conn:
                    return  # Already cleaned up

                # If this was the primary connection, clean up services
                if self.cdp == conn.cdp:
                    if self.fetch.enabled:
                        self.fetch.enabled = False
                    self.dom.clear_selections()
                    self.dom.cleanup()
                    self.enabled_domains.clear()

                    # Set error state with disconnect info
                    self.state.error_state = {"message": f"{target}: {user_reason}", "timestamp": time.time()}

            # Notify SSE clients
            self._trigger_broadcast()

            logger.info(f"Unexpected disconnect cleanup completed for {target}")

        except Exception as e:
            logger.error(f"Error during unexpected disconnect cleanup for {target}: {e}")
