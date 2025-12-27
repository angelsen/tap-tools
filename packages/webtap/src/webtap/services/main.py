"""Main service orchestrator for WebTap business logic.

PUBLIC API:
  - WebTapService: Orchestrator for all domain services
  - TargetState: Per-target connection state enum
  - ActiveConnection: Tracks an active CDP connection
"""

from typing import Any
from dataclasses import dataclass
from enum import Enum
import time

from webtap.filters import FilterManager
from webtap.notices import NoticeManager
from webtap.services.fetch import FetchService
from webtap.services.network import NetworkService
from webtap.services.console import ConsoleService
from webtap.services.dom import DOMService
from webtap.services.state_snapshot import StateSnapshot


class TargetState(str, Enum):
    """Per-target connection state."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


@dataclass
class ActiveConnection:
    """Tracks an active CDP connection."""

    target: str
    cdp: "Any"  # CDPSession
    page_info: dict
    connected_at: float
    state: TargetState = TargetState.CONNECTED


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
        self._state_lock = threading.RLock()  # Reentrant lock - safe to acquire multiple times by same thread

        # Multi-target connection tracking
        self.connections: dict[str, ActiveConnection] = {}  # keyed by target string
        self.tracked_targets: list[str] = []  # Default scope for aggregation

        self.enabled_domains: set[str] = set()
        self.filters = FilterManager()
        self.notices = NoticeManager()

        # RPC framework (set by server.py after initialization)
        self.rpc: "Any | None" = None

        self.fetch = FetchService()
        self.network = NetworkService()
        self.console = ConsoleService()
        self.dom = DOMService()

        # Wire services to this service instance
        self.fetch.set_service(self)
        self.network.set_service(self)
        self.console.set_service(self)
        self.dom.set_service(self)

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

    def get_tracked_or_all(self) -> list[str]:
        """Get tracked targets, or all connected if none tracked.

        Returns:
            List of target IDs to use for aggregation
        """
        if self.tracked_targets:
            return [t for t in self.tracked_targets if t in self.connections]
        return list(self.connections.keys())

    def get_cdps(self, targets: list[str] | None = None) -> list["Any"]:
        """Get CDPSessions for specified targets (or tracked/all).

        Args:
            targets: Explicit target list, or None to use tracked/all

        Returns:
            List of CDPSession instances
        """
        target_list = targets if targets is not None else self.get_tracked_or_all()
        return [self.connections[t].cdp for t in target_list if t in self.connections]

    def set_tracked_targets(self, targets: list[str] | None) -> list[str]:
        """Set tracked targets. None or [] clears (meaning all).

        Args:
            targets: List of target IDs to track, or None/[] for all

        Returns:
            Updated tracked targets list
        """
        self.tracked_targets = list(targets) if targets else []
        self._trigger_broadcast()
        return self.tracked_targets

    def _create_snapshot(self) -> StateSnapshot:
        """Create immutable state snapshot from current state.

        MUST be called with self._state_lock held to ensure atomic read.

        Returns:
            Frozen StateSnapshot with current state
        """
        import copy

        # Connection state - any active connections
        connected = len(self.connections) > 0

        # Legacy fields (empty - no primary connection)
        page_id = ""
        page_title = ""
        page_url = ""

        # Event count - aggregate from all connections
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
        tracked_targets = tuple(self.tracked_targets)
        connections = tuple(
            {
                "target": conn.target,
                "title": conn.page_info.get("title", ""),
                "url": conn.page_info.get("url", ""),
                "state": conn.state.value,
                "devtools_url": conn.page_info.get("devtoolsFrontendUrl", ""),
            }
            for conn in self.connections.values()
        )

        # Browser/DOM state (get_state() is already thread-safe internally)
        browser_state = self.dom.get_state()

        # Error state - convert to dict of errors by target
        error_state = self.state.error_state
        if not isinstance(error_state, dict):
            error_state = {}
        errors_dict = dict(error_state)  # Copy for immutability

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
            tracked_targets=tracked_targets,
            connections=connections,
            inspect_active=browser_state["inspect_active"],
            inspecting_target=browser_state.get("inspecting"),
            selections=selections,  # Deep copy ensures nested dicts are immutable
            prompt=browser_state["prompt"],
            pending_count=browser_state["pending_count"],
            errors=errors_dict,
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
        """Total count of all CDP events stored across all connections."""
        total = 0
        for conn in self.connections.values():
            try:
                result = conn.cdp.query("SELECT COUNT(*) FROM events")
                total += result[0][0] if result else 0
            except Exception:
                pass
        return total

    def register_port(self, port: int) -> dict:
        """Register a Chrome debug port with validation.

        Args:
            port: Port number (1024-65535)

        Returns:
            {"port": N, "status": "registered"|"unreachable", "warning": ...}

        Raises:
            ValueError: If port out of range
        """
        import httpx

        if not (1024 <= port <= 65535):
            raise ValueError(f"Invalid port: {port}. Must be 1024-65535")

        # Check if Chrome is listening (outside lock)
        try:
            response = httpx.get(f"http://localhost:{port}/json", timeout=2.0)
            if response.status_code != 200:
                return {
                    "port": port,
                    "status": "unreachable",
                    "warning": f"Port {port} not responding with Chrome debug protocol",
                }
        except httpx.RequestError:
            return {
                "port": port,
                "status": "unreachable",
                "warning": f"Port {port} not responding. Is Chrome running with --remote-debugging-port={port}?",
            }

        # State mutation (inside lock)
        with self._state_lock:
            if port not in self.state.cdp_sessions:
                from webtap.cdp import CDPSession

                self.state.cdp_sessions[port] = CDPSession(port=port)

        self._trigger_broadcast()
        return {"port": port, "status": "registered"}

    def unregister_port(self, port: int) -> dict:
        """Unregister port and disconnect any connections on it.

        Args:
            port: Port number to remove

        Returns:
            {"port": N, "removed": True, "disconnected": [...]}

        Raises:
            ValueError: If port is 9222 (protected)
        """
        from webtap.targets import parse_target

        if port == 9222:
            raise ValueError("Port 9222 is protected (default desktop port)")

        if not hasattr(self.state, "cdp_sessions") or port not in self.state.cdp_sessions:
            return {"port": port, "removed": False}

        # Disconnect targets on this port
        disconnected = []
        for target_id in list(self.connections.keys()):
            target_port, _ = parse_target(target_id)
            if target_port == port:
                self.disconnect_target(target_id)
                disconnected.append(target_id)

        # Remove session (inside lock)
        with self._state_lock:
            session = self.state.cdp_sessions.pop(port, None)

        if session:
            session.cleanup()

        self._trigger_broadcast()
        return {"port": port, "removed": True, "disconnected": disconnected}

    def list_ports(self) -> dict:
        """List registered ports with page/connection counts.

        Returns:
            {"ports": [{"port": N, "page_count": N, "connection_count": N, "status": str}]}
        """
        if not hasattr(self.state, "cdp_sessions"):
            return {"ports": []}

        # Get all pages via existing method
        pages_result = self.list_pages()
        all_pages = pages_result.get("pages", [])

        # Aggregate by port
        port_stats: dict[int, dict] = {p: {"page_count": 0, "connection_count": 0} for p in self.state.cdp_sessions}

        for page in all_pages:
            port = page.get("chrome_port")
            if port in port_stats:
                port_stats[port]["page_count"] += 1
                if page.get("connected"):
                    port_stats[port]["connection_count"] += 1

        ports = [
            {"port": port, **stats, "status": "active" if stats["page_count"] > 0 else "reachable"}
            for port, stats in port_stats.items()
        ]
        return {"ports": ports}

    def set_error(self, message: str, target: str | None = None) -> None:
        """Set error state with locking and broadcast.

        Args:
            message: Error message
            target: Target ID. If None, uses "global" key for backward compatibility.
        """
        import time

        error_key = target or "global"
        with self._state_lock:
            if not isinstance(self.state.error_state, dict):
                self.state.error_state = {}
            self.state.error_state[error_key] = {"message": message, "timestamp": time.time()}
        self._trigger_broadcast()

    def clear_error(self, target: str | None = None) -> None:
        """Clear error state with locking and broadcast.

        Args:
            target: Target ID to clear. If None, clears all errors.
        """
        with self._state_lock:
            if target:
                self.state.error_state.pop(target, None)
            else:
                self.state.error_state = {}
        self._trigger_broadcast()

    def get_connection(self, target: str) -> ActiveConnection | None:
        """Get active connection by target ID.

        Args:
            target: Target ID in format "{port}:{short-id}"

        Returns:
            ActiveConnection if exists, None otherwise
        """
        return self.connections.get(target)

    def resolve_cdp(
        self,
        row_id: int,
        table: str,
        id_column: str = "id",
        target: str | None = None,
    ) -> Any | None:
        """Find CDPSession by target or by searching for row.

        Args:
            row_id: Row ID to search for
            table: Table to search in (e.g., "har_summary", "events")
            id_column: Column to match (default "id", use "rowid" for events)
            target: Specific target to use. If provided, skips search.

        Returns:
            CDPSession if found, None otherwise
        """
        if target:
            conn = self.connections.get(target)
            return conn.cdp if conn else None

        for conn in self.connections.values():
            if conn.cdp.query(f"SELECT 1 FROM {table} WHERE {id_column} = ? LIMIT 1", [row_id]):
                return conn.cdp
        return None

    def connect_to_page(
        self,
        page_index: int | None = None,
        page_id: str | None = None,
        chrome_port: int | None = None,
        target: str | None = None,
    ) -> dict[str, Any]:
        """Connect to Chrome page and enable required domains.

        Each connection creates a NEW CDPSession. Supports multiple simultaneous connections.

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
        from webtap.cdp import CDPSession
        from webtap.targets import make_target, resolve_target, parse_target

        # Resolve target from different input methods
        target_page = None
        if target:
            # Target provided directly - parse it
            port, short_id = parse_target(target)

            # Check if already connected
            if target in self.connections:
                existing = self.connections[target]
                return {
                    "title": existing.page_info.get("title", "Untitled"),
                    "url": existing.page_info.get("url", ""),
                    "target": existing.target,
                    "already_connected": True,
                }

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

        # Create NEW CDPSession for this page
        cdp = CDPSession(port=chrome_port)

        # Connect to the page (pass target_page to avoid duplicate list_pages call)
        cdp.connect(page_index=page_index, page_id=page_id, page_info=target_page)

        # Enable required domains in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed

        failures = {}
        with ThreadPoolExecutor(max_workers=len(_REQUIRED_DOMAINS)) as executor:
            futures = {executor.submit(cdp.execute, f"{domain}.enable"): domain for domain in _REQUIRED_DOMAINS}
            for future in as_completed(futures):
                domain = futures[future]
                try:
                    future.result()
                except Exception as e:
                    failures[domain] = str(e)

        if failures:
            cdp.disconnect()
            raise RuntimeError(f"Failed to enable domains: {failures}")

        # Get page info and create target ID
        page_info = cdp.page_info or {}
        full_page_id = page_info.get("id", "")
        target_id = make_target(chrome_port, full_page_id)

        # Set target on CDPSession for event tagging
        cdp.target = target_id

        # Store connection
        with self._state_lock:
            connection = ActiveConnection(
                target=target_id,
                cdp=cdp,
                page_info=page_info,
                connected_at=time.time(),
                state=TargetState.CONNECTED,
            )
            self.connections[target_id] = connection

        # Register callbacks for this session
        cdp.set_disconnect_callback(lambda code, reason: self._handle_unexpected_disconnect(target_id, code, reason))
        cdp.set_broadcast_callback(self._trigger_broadcast)

        # If fetch is enabled globally, enable it on this new connection
        if self.fetch.enabled:
            try:
                cdp.execute("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
            except Exception:
                pass  # Non-fatal

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

        # Set DISCONNECTING state before cleanup
        with self._state_lock:
            conn.state = TargetState.DISCONNECTING
        self._trigger_broadcast()

        # Disconnect CDP first (network I/O - outside lock)
        conn.cdp.disconnect()
        conn.cdp.cleanup()  # Cleanup DuckDB thread

        # All state mutations inside lock
        with self._state_lock:
            self.connections.pop(target, None)

            # Remove from tracked targets if present
            if target in self.tracked_targets:
                self.tracked_targets.remove(target)

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
            self.clear_error()

        self.enabled_domains.clear()
        self._trigger_broadcast()

    def enable_domains(self, domains: list[str]) -> dict[str, str]:
        """Enable CDP domains on all connected targets.

        Args:
            domains: List of domain names to enable
        """
        failures = {}
        for conn in self.connections.values():
            for domain in domains:
                try:
                    conn.cdp.execute(f"{domain}.enable")
                    self.enabled_domains.add(domain)
                except Exception as e:
                    failures[f"{conn.target}:{domain}"] = str(e)
        return failures

    def clear_events(self) -> dict[str, Any]:
        """Clear all stored CDP events across all connections."""
        for conn in self.connections.values():
            conn.cdp.clear_events()
        self._trigger_broadcast()
        return {"cleared": True, "events": 0}

    def list_pages(self, chrome_port: int | None = None) -> dict[str, Any]:
        """List available Chrome pages with target IDs.

        Args:
            chrome_port: Specific port to query. If None, queries registered ports.

        Returns:
            Dict with 'pages' list. Each page includes 'target', 'connected' fields.
        """
        import httpx
        from webtap.targets import make_target

        all_pages = []

        # Query specific port or all registered ports
        if chrome_port:
            ports_to_query = [chrome_port]
        else:
            ports_to_query = list(self.state.registered_ports)

        for port in ports_to_query:
            try:
                # Direct HTTP request to /json endpoint
                resp = httpx.get(f"http://localhost:{port}/json", timeout=2.0)
                pages = resp.json()

                # Filter and add metadata to each page
                for page in pages:
                    if page.get("type") != "page":
                        continue

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

    def execute_on_target(self, target: str, callback: "Any") -> "Any":
        """Execute callback on an existing target connection.

        Args:
            target: Target ID in format "{port}:{short-id}"
            callback: Function that receives CDPSession and returns result

        Returns:
            Return value from callback

        Raises:
            ValueError: If target not connected
        """
        conn = self.get_connection(target)
        if not conn:
            raise ValueError(f"Target '{target}' not connected")
        return callback(conn.cdp)

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

                # Remove from tracked targets if present
                if target in self.tracked_targets:
                    self.tracked_targets.remove(target)

            # Set error state outside lock (set_error acquires its own lock)
            self.set_error(user_reason, target=target)

            # Notify SSE clients
            self._trigger_broadcast()

            logger.info(f"Unexpected disconnect cleanup completed for {target}")

        except Exception as e:
            logger.error(f"Error during unexpected disconnect cleanup for {target}: {e}")


__all__ = ["WebTapService", "TargetState", "ActiveConnection"]
