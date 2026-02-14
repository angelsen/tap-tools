"""Main service orchestrator for WebTap business logic.

PUBLIC API:
  - WebTapService: Orchestrator for all domain services
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from webtap.cdp import CDPSession
from webtap.filters import FilterManager
from webtap.notices import NoticeManager
from webtap.services.connection import ActiveConnection, ConnectionManager
from webtap.services.console import ConsoleService
from webtap.services.dom import DOMService
from webtap.services.fetch import FetchService
from webtap.services.network import NetworkService
from webtap.services.state_snapshot import StateSnapshot
from webtap.services.watcher import ChromeWatcher


_DOMAINS_BY_TYPE = {
    "page": ["Page", "Network", "Runtime", "Log", "DOMStorage"],
    "service_worker": ["Network", "Runtime", "Log"],
    "background_page": ["Network", "Runtime", "Log", "DOMStorage"],
    "worker": ["Network", "Runtime"],
}

# Connectable target types (exclude iframes, other, etc.)
_CONNECTABLE_TYPES = {"page", "service_worker", "background_page", "worker"}

# Target types watched by URL (target_id changes on extension reload)
_URL_WATCHED_TYPES = {"service_worker", "background_page"}

# Network.enable buffer sizes
_NETWORK_BUFFER_SIZE = 50_000_000  # 50MB total buffer
_NETWORK_RESOURCE_SIZE = 10_000_000  # 10MB per resource
_MAX_DETACHED_URLS = 50  # Max URL mappings for old target ID resolution
_DOMAIN_ENABLE_TIMEOUT = 10  # Healthy targets respond in <1s


def _is_url_watched(target_info: dict) -> bool:
    """Targets watched by URL (stable) rather than target_id.

    - service_worker, background_page: target_id changes on extension reload
    - Extension pages (popup, sidepanel): destroyed/recreated with new IDs
    - Regular pages, workers: watched by target_id (tab identity stable)
    """
    target_type = target_info.get("type", "")
    if target_type in _URL_WATCHED_TYPES:
        return True
    url = target_info.get("url", "")
    return url.startswith("chrome-extension://") and target_type in {"page", "other"}


class WebTapService:
    """Main service orchestrating all WebTap domain services.

    Coordinates CDP session management, domain services, and filter management.
    Shared between REPL commands and API endpoints for consistent state.

    Attributes:
        state: WebTap application state instance.
        conn_mgr: Connection lifecycle manager for multi-target support.
        enabled_domains: Set of currently enabled CDP domains.
        filters: Filter manager for event filtering.
        notices: Notice manager for multi-surface notifications.
        fetch: Fetch interception service.
        network: Network monitoring service.
        console: Console message service.
        dom: DOM inspection and element selection service.
    """

    def __init__(self, state):
        """Initialize service orchestrator.

        Args:
            state: Application state instance
        """
        import threading

        self.state = state
        self._state_lock = threading.RLock()

        # Browser sessions (one per Chrome port)
        self._browsers: dict[int, "Any"] = {}  # port -> BrowserSession (avoid import cycle)

        # Connection lifecycle manager
        self.conn_mgr = ConnectionManager()
        self.tracked_targets: list[str] = []

        self.enabled_domains: set[str] = set()
        self.filters = FilterManager()
        self.notices = NoticeManager()

        # Set by server.py after initialization
        self.rpc: "Any | None" = None

        # Domain services
        self.fetch = FetchService()
        self.network = NetworkService()
        self.console = ConsoleService()
        self.dom = DOMService()

        self.fetch.set_service(self)
        self.network.set_service(self)
        self.console.set_service(self)
        self.dom.set_service(self)

        # Chrome availability watcher
        self.watcher = ChromeWatcher(self)

        # Set by API server
        self._broadcast_queue: "Any | None" = None

        # Prevents duplicate broadcasts during rapid CDP events
        self._broadcast_pending = threading.Event()

        # Background session setup (domain enables)
        self._setup_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="session-setup")

        # Cache for selections deepcopy optimization
        self._cached_selections: dict | None = None
        self._cached_selections_keys: frozenset | None = None

        # URL map for disconnected URL-watched targets (target_id -> url)
        # Enables get_connection() to resolve old target IDs to new connections
        self._detached_urls: dict[str, str] = {}  # target_id -> url

        # Stashed CDPSessions for disconnected URL-watched targets (url -> CDPSession)
        # DuckDB stays alive for read-only queries; callbacks/fetch/broadcast cleared
        self._stashed_dbs: dict[str, CDPSession] = {}  # url -> CDPSession (DB only)

        # Self-target detection (learned from extension RPC header)
        self._own_extension_id: str | None = None
        self._has_silent_sessions = False

        # Updated atomically on state change, read without locks
        self._state_snapshot: StateSnapshot = StateSnapshot.create_empty()

    def _get_or_create_browser(self, port: int) -> "Any":
        """Get existing or create new BrowserSession for port.

        Args:
            port: Chrome debug port

        Returns:
            BrowserSession instance for this port
        """
        from webtap.cdp import BrowserSession

        if port not in self._browsers:
            browser = BrowserSession(port=port)
            browser.connect()
            self._browsers[port] = browser
        return self._browsers[port]

    @property
    def connections(self) -> dict[str, ActiveConnection]:
        """Active connections, delegated to ConnectionManager."""
        return self.conn_mgr.connections

    def set_broadcast_queue(self, queue: "Any") -> None:
        """Set queue for broadcasting state changes.

        Args:
            queue: asyncio.Queue for thread-safe signaling
        """
        self._broadcast_queue = queue

    def start(self) -> None:
        """Start background services. Called when daemon starts."""
        self.watcher.start()

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
            List of active CDPSession instances
        """
        target_list = targets if targets is not None else self.get_tracked_or_all()
        return [self.connections[t].cdp for t in target_list if t in self.connections]

    def get_query_cdps(self, targets: list[str] | None = None) -> list["Any"]:
        """Get CDPSessions for queries, including stashed DBs from disconnected targets.

        Unlike get_cdps() which returns only active sessions (for js, navigate, etc.),
        this includes stashed CDPSessions whose DuckDB is still alive for read-only queries.

        Args:
            targets: Explicit target list, or None to include tracked/all + stashed

        Returns:
            List of CDPSession instances (active + stashed when targets is None)
        """
        active = self.get_cdps(targets)
        if targets is not None:
            return active
        return active + list(self._stashed_dbs.values())

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

    def watch_targets(self, targets: list[str]) -> dict:
        """Watch one or more targets. Replaces connect_to_page()."""
        from webtap.targets import make_target, parse_target

        results = []
        for target in targets:
            port, short_id = parse_target(target)
            browser = self._get_or_create_browser(port)

            # Register lifecycle callbacks if not set
            if not browser._on_target_created:
                browser.set_target_lifecycle_callbacks(
                    on_created=self._handle_target_created,
                    on_info_changed=self._handle_target_info_changed,
                    on_sw_crashed=self._handle_sw_crashed,
                    on_sw_reloaded=self._handle_sw_reloaded,
                )

            # Resolve full target info
            all_targets = browser.list_all_targets()
            resolved = None
            for t in all_targets:
                if make_target(port, t["targetId"]) == target:
                    resolved = t
                    break
            if not resolved:
                results.append({"target": target, "error": "not found"})
                continue
            if resolved.get("type") == "worker" and not resolved.get("url"):
                results.append({"target": target, "error": "worker has no URL (zombie target)"})
                continue

            # Add to appropriate watched set + expand URL-watched URLs
            if _is_url_watched(resolved):
                url = resolved.get("url", "")
                browser.watch_url(url, resolved)
                # Blanket: also watch all other current targets with same URL
                for t in all_targets:
                    other_id = make_target(port, t["targetId"])
                    if t.get("url") == url and other_id != target and other_id not in self.connections:
                        try:
                            sid = browser.attach(t["targetId"])
                            cdp = self._register_session(browser, sid, t, other_id, port)
                            self._finish_setup(other_id, cdp, t)
                            results.append({"target": other_id, "watched": True, "state": "attached"})
                        except Exception:
                            pass
            else:
                browser.watch_target(target, resolved)

            # If target is currently running, attach now
            if target not in self.connections:
                try:
                    session_id = browser.attach(resolved["targetId"])
                    cdp = self._register_session(browser, session_id, resolved, target, port)
                    self._finish_setup(target, cdp, resolved)
                    results.append({"target": target, "watched": True, "state": "attached"})
                except Exception as e:
                    results.append({"target": target, "watched": True, "attached": False, "error": str(e)})
            else:
                results.append({"target": target, "watched": True, "attached": True, "already_attached": True})

        self._trigger_broadcast()
        return {"watched": results}

    def unwatch_targets(self, targets: list[str] | None = None) -> dict:
        """Stop watching targets. Replaces disconnect_target()/disconnect()."""
        from webtap.targets import parse_target

        if targets is None:
            # Unwatch all -- collect connected targets + clear watches atomically
            targets = []
            for browser in self._browsers.values():
                cleared_ids, cleared_urls = browser.clear_all_watches()
                targets.extend(cleared_ids)
                # Find connected targets for cleared URLs
                for url in cleared_urls:
                    for tid, conn in self.connections.items():
                        if conn.cdp.target_info.get("url") == url:
                            targets.append(tid)
                    # Clear URL mappings for cleared URLs
                    self._detached_urls = {tid: u for tid, u in self._detached_urls.items() if u != url}
                    # Clean up stashed DB for this URL
                    stashed = self._stashed_dbs.pop(url, None)
                    if stashed:
                        stashed.cleanup()

        results = []
        for target in targets:
            port, _ = parse_target(target)
            browser = self._browsers.get(port)
            if browser:
                browser.unwatch_target(target)
                # Also remove from URL watch if this target's URL is watched
                if target in self.connections:
                    url = self.connections[target].cdp.target_info.get("url", "")
                    browser.unwatch_url(url)
                    # Clear URL mappings for this URL
                    self._detached_urls = {tid: u for tid, u in self._detached_urls.items() if u != url}
                    # Clean up stashed DB for this URL
                    stashed = self._stashed_dbs.pop(url, None)
                    if stashed:
                        stashed.cleanup()

            # If attached, detach
            if target in self.connections:
                conn = self.connections[target]
                self.fetch.cleanup_target(target, conn.cdp)
                self.conn_mgr.disconnect(target)
                self.conn_mgr.remove_from_tracked(target, self.tracked_targets)

            results.append({"target": target, "unwatched": True})

        self._trigger_broadcast()
        return {"unwatched": results}

    def _register_session(self, browser, session_id: str, target_info: dict, target_id: str, port: int) -> CDPSession:
        """Register CDPSession and connection entry. Returns CDPSession."""
        from webtap.services.connection import TargetState

        cdp = CDPSession(browser, session_id, target_info, port)
        browser.register_session(session_id, cdp)
        cdp.target = target_id

        page_info = {
            "title": target_info.get("title", "Untitled"),
            "url": target_info.get("url", ""),
            "type": target_info.get("type", "page"),
        }

        self.conn_mgr.connect(target_id, cdp, page_info, initial_state=TargetState.CONNECTING)
        cdp.set_disconnect_callback(lambda code, reason: self._handle_disconnect(target_id, code, reason))

        # Skip broadcast callback on self-targets to prevent feedback loop
        target_url = target_info.get("url", "")
        is_self_target = self._own_extension_id and target_url.startswith(
            f"chrome-extension://{self._own_extension_id}/"
        )
        if is_self_target:
            if not self._has_silent_sessions:
                self._start_periodic_broadcast()
        else:
            cdp.set_broadcast_callback(self._trigger_broadcast)

        return cdp

    def _finish_setup(self, target_id: str, cdp: CDPSession, target_info: dict) -> None:
        """Enable CDP domains and transition to ATTACHED. Runs in background thread."""
        from webtap.services.connection import TargetState

        logger = logging.getLogger(__name__)

        try:
            target_type = target_info.get("type", "page")
            domains_to_enable = _DOMAINS_BY_TYPE.get(target_type, _DOMAINS_BY_TYPE["page"])

            failures = {}
            with ThreadPoolExecutor(max_workers=len(domains_to_enable)) as executor:
                futures = {}
                for domain in domains_to_enable:
                    if domain == "Network":
                        future = executor.submit(
                            cdp.execute,
                            "Network.enable",
                            {
                                "maxTotalBufferSize": _NETWORK_BUFFER_SIZE,
                                "maxResourceBufferSize": _NETWORK_RESOURCE_SIZE,
                            },
                            _DOMAIN_ENABLE_TIMEOUT,
                        )
                    else:
                        future = executor.submit(cdp.execute, f"{domain}.enable", None, _DOMAIN_ENABLE_TIMEOUT)
                    futures[future] = domain

                for future in as_completed(futures):
                    domain = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        failures[domain] = str(e)

            if failures:
                logger.warning(f"Failed to enable domains on {target_id}: {failures}")

            self.fetch.enable_on_target(target_id, cdp)
            self._register_body_capture_callback(cdp)
            self.filters.load()

        except Exception as e:
            logger.error(f"Setup failed for {target_id}: {e}")

        finally:
            self.conn_mgr.set_state(target_id, TargetState.ATTACHED)
            self._trigger_broadcast()

    def _handle_disconnect(self, target_id: str, code: int, reason: str) -> None:
        """Handle target disconnect. Preserve CDPSession for URL-watched targets."""
        from webtap.targets import parse_target

        logger = logging.getLogger(__name__)
        logger.info(f"Target disconnected: {target_id} (code={code}, reason={reason})")

        port, _ = parse_target(target_id)
        browser = self._browsers.get(port)

        # Check if this was a URL-watched (ephemeral) target
        conn = self.connections.get(target_id)
        if conn and browser:
            url = conn.cdp.target_info.get("url", "")
            if browser.is_watched("", url):
                # Record URL mapping for target resolution
                self._detached_urls[target_id] = url
                # Evict oldest entries if over limit
                while len(self._detached_urls) > _MAX_DETACHED_URLS:
                    oldest_key = next(iter(self._detached_urls))
                    del self._detached_urls[oldest_key]

                # Clean up live state but keep DuckDB alive for queries
                self.fetch.cleanup_target(target_id, conn.cdp)
                conn.cdp._event_callbacks.clear()
                conn.cdp._broadcast_callback = None

                # Stash DB (clean up old stash for same URL first)
                old_stash = self._stashed_dbs.get(url)
                if old_stash:
                    old_stash.cleanup()
                self._stashed_dbs[url] = conn.cdp

                self.conn_mgr.remove(target_id)
                self.conn_mgr.remove_from_tracked(target_id, self.tracked_targets)
                self._update_silent_sessions()
                self._trigger_broadcast()
                return

        # Normal disconnect cleanup
        if conn:
            self.fetch.cleanup_target(target_id, conn.cdp)
        self.conn_mgr.remove(target_id)
        self.conn_mgr.remove_from_tracked(target_id, self.tracked_targets)
        self._update_silent_sessions()
        self._trigger_broadcast()

    def _handle_target_created(self, target_info: dict, target_id: str) -> None:
        """Called by BrowserSession when a watched or opener-matched target appears.

        Runs on WS thread — must not call execute(). Submits attach+setup to executor.
        """
        self._setup_executor.submit(self._attach_watched_target, target_info, target_id)

    def _attach_watched_target(self, target_info: dict, target_id: str) -> None:
        """Attach to a watched or opener-matched target. Runs in executor thread."""
        from webtap.targets import parse_target

        port, _ = parse_target(target_id)
        browser = self._browsers.get(port)
        if not browser or target_id in self.connections:
            return

        try:
            chrome_target_id = target_info.get("targetId", "")
            session_id = browser.attach(chrome_target_id)
            cdp = self._register_session(browser, session_id, target_info, target_id, port)
            self._finish_setup(target_id, cdp, target_info)
            # Mark as auto-attached if not explicitly watched (opener-matched popup)
            # Also add to watched set so grandchildren resolve via opener matching
            conn = self.connections.get(target_id)
            if conn and not browser.is_watched(target_id, target_info.get("url", "")):
                conn.auto_attached = True
                browser.watch_target(target_id, target_info)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to re-attach watched target {target_id}: {e}")

    def _handle_target_info_changed(self, target_info: dict) -> None:
        """Update connection metadata when target navigates or changes title."""
        from webtap.targets import make_target

        for browser in self._browsers.values():
            target_id = make_target(browser.port, target_info.get("targetId", ""))
            conn = self.connections.get(target_id)
            if conn:
                conn.page_info["title"] = target_info.get("title", conn.page_info.get("title", ""))
                conn.page_info["url"] = target_info.get("url", conn.page_info.get("url", ""))
                self._trigger_broadcast()
                return

    def _handle_sw_crashed(self, session_id: str) -> None:
        """SW idle stop. Session stays, renderer disconnected. Mark suspended."""
        from webtap.services.connection import TargetState

        for browser in self._browsers.values():
            cdp = browser.get_session(session_id)
            if cdp:
                if cdp.target and cdp.target in self.connections:
                    self.conn_mgr.set_state(cdp.target, TargetState.SUSPENDED)
                    self._trigger_broadcast()
                return

    def _handle_sw_reloaded(self, session_id: str) -> None:
        """SW restart after idle. Re-enable domains on existing session."""
        from webtap.services.connection import TargetState

        for browser in self._browsers.values():
            cdp = browser.get_session(session_id)
            if cdp:
                if cdp.target and cdp.target in self.connections:
                    # Re-enable domains -- renderer state was lost
                    target_type = cdp.target_info.get("type", "page")
                    domains = _DOMAINS_BY_TYPE.get(target_type, ["Network", "Runtime"])
                    for domain in domains:
                        try:
                            cdp.execute(f"{domain}.enable")
                        except Exception:
                            pass
                    # Re-enable fetch interception if it was active
                    self.fetch.enable_on_target(cdp.target, cdp)
                    self._register_body_capture_callback(cdp)
                    self.conn_mgr.set_state(cdp.target, TargetState.ATTACHED)
                    self._trigger_broadcast()
                return

    def list_targets(self, chrome_port: int | None = None) -> dict:
        """List all targets with watched/attached state. Replaces list_pages()."""
        import httpx
        from webtap.targets import make_target

        all_targets = []
        ports = [chrome_port] if chrome_port else list(self.state.registered_ports)

        for port in ports:
            browser = self._browsers.get(port)
            if browser:
                targets = browser.list_all_targets()
            else:
                try:
                    resp = httpx.get(f"http://localhost:{port}/json", timeout=2.0)
                    raw = resp.json()
                    targets = []
                    for t in raw:
                        t["targetId"] = t.pop("id", "")
                        targets.append(t)
                except Exception:
                    continue

            # Build opener lookup (CDP targetId -> our target format)
            opener_map = {}
            for t in targets:
                if t.get("type") in _CONNECTABLE_TYPES:
                    opener_map[t.get("targetId", "")] = make_target(port, t["targetId"])

            for t in targets:
                if t.get("type") not in _CONNECTABLE_TYPES:
                    continue
                if t.get("type") == "worker" and not t.get("url"):
                    continue
                url = t.get("url", "")
                if url.startswith("chrome://"):
                    continue
                target_id = make_target(port, t["targetId"])
                watched = browser is not None and browser.is_watched(target_id, url)
                attached = target_id in self.connections
                state = self.connections[target_id].state.value if attached else ""
                opener = t.get("openerId", "")
                parent = opener_map.get(opener, "") if opener else ""
                auto_attached = attached and self.connections[target_id].auto_attached
                all_targets.append(
                    {
                        "target": target_id,
                        "type": t.get("type", "page"),
                        "title": t.get("title", "Untitled"),
                        "url": url,
                        "chrome_port": port,
                        "watched": watched,
                        "attached": attached,
                        "auto_attached": auto_attached,
                        "state": state,
                        "parent": parent,
                    }
                )

        return {"targets": all_targets}

    def _create_snapshot(self) -> StateSnapshot:
        """Create immutable state snapshot from current state.

        Thread-safe - reads from ConnectionManager and services that have
        their own locking. No external lock required.

        Returns:
            Frozen StateSnapshot with current state
        """
        import copy

        # Connection state - any active connections
        connected = len(self.connections) > 0

        # Event count - aggregate from all connections
        event_count = self.event_count

        # Fetch state (now always-on capture with per-target rules)
        fetch_status = self.fetch.get_status()
        fetch_enabled = fetch_status["capture"]
        fetch_rules = fetch_status["rules"] if fetch_status["rules"] else None
        capture_count = fetch_status["capture_count"]

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
                "type": conn.page_info.get("type", "page"),
                "state": conn.state.value,
                "devtools_url": conn.page_info.get("devtoolsFrontendUrl", ""),
                "auto_attached": conn.auto_attached,
            }
            for conn in self.connections.values()
        )

        # Watch state -- aggregate from all browser sessions (thread-safe snapshots)
        all_watched_targets: list[str] = []
        all_watched_urls: list[str] = []
        for browser in self._browsers.values():
            targets_snap, urls_snap = browser.get_watched_snapshot()
            all_watched_targets.extend(targets_snap)
            all_watched_urls.extend(urls_snap)
        watched_targets = tuple(all_watched_targets)
        watched_urls = tuple(all_watched_urls)

        # Browser/DOM state (get_state() is already thread-safe internally)
        browser_state = self.dom.get_state()

        # Error state - convert to dict of errors by target
        error_state = self.state.error_state
        if not isinstance(error_state, dict):
            error_state = {}
        errors_dict = dict(error_state)  # Copy for immutability

        # Optimized selections copy - reuse cached copy if unchanged
        source_selections = browser_state["selections"]
        source_keys = frozenset(source_selections.keys()) if source_selections else frozenset()

        if source_keys == self._cached_selections_keys and self._cached_selections is not None:
            selections = self._cached_selections
        else:
            selections = copy.deepcopy(source_selections)
            self._cached_selections = selections
            self._cached_selections_keys = source_keys

        return StateSnapshot(
            connected=connected,
            event_count=event_count,
            fetch_enabled=fetch_enabled,
            fetch_rules=fetch_rules,
            capture_count=capture_count,
            enabled_filters=enabled_filters,
            disabled_filters=disabled_filters,
            tracked_targets=tracked_targets,
            connections=connections,
            watched_targets=watched_targets,
            watched_urls=watched_urls,
            inspect_active=browser_state["inspect_active"],
            inspecting_target=browser_state.get("inspecting"),
            selections=selections,  # Deep copy ensures nested dicts are immutable
            prompt=browser_state["prompt"],
            pending_count=browser_state["pending_count"],
            errors=errors_dict,
            notices=self.notices.get_all(),
            epoch=self.conn_mgr.epoch,
            tracked_clients=self.rpc.get_tracked_clients() if self.rpc else {},
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
        logger = logging.getLogger(__name__)

        # Early exit if no queue (API not started yet)
        if not self._broadcast_queue:
            return

        # Check coalescing flag FIRST (fast, avoids expensive snapshot creation)
        with self._state_lock:
            if self._broadcast_pending.is_set():
                return  # Another thread will broadcast soon, skip entirely
            self._broadcast_pending.set()

        # Create snapshot OUTSIDE lock (potentially slow, no lock contention)
        # Only reached if we're the thread that will broadcast
        try:
            snapshot = self._create_snapshot()
        except (TypeError, AttributeError) as e:
            self._broadcast_pending.clear()  # Clear flag on error
            logger.error(f"Programming error in snapshot creation: {e}")
            raise
        except Exception as e:
            self._broadcast_pending.clear()  # Clear flag on error
            logger.error(f"Failed to create state snapshot: {e}", exc_info=True)
            return

        # Atomic swap (fast, minimal lock time)
        with self._state_lock:
            self._state_snapshot = snapshot

        # Signal broadcast (outside lock - queue.put_nowait is thread-safe)
        try:
            self._broadcast_queue.put_nowait({"type": "state_change"})
        except Exception as e:
            # Clear flag if queue failed so next trigger can try
            self._broadcast_pending.clear()
            logger.warning(f"Failed to queue broadcast: {e}")

    def _update_silent_sessions(self) -> None:
        """Update silent session flag after connection changes."""
        self._has_silent_sessions = any(conn.cdp._broadcast_callback is None for conn in self.connections.values())

    def _start_periodic_broadcast(self) -> None:
        """Start 1s periodic broadcast for silent (self-target) sessions."""
        import threading

        self._has_silent_sessions = True

        def _periodic():
            while self._has_silent_sessions:
                self._trigger_broadcast()
                threading.Event().wait(1.0)

        threading.Thread(target=_periodic, daemon=True, name="periodic-broadcast").start()

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

    def set_browser_selection(self, selection_id: str, data: dict) -> None:
        """Set a browser selection, initializing browser_data if needed.

        Args:
            selection_id: Unique ID for this selection
            data: Selection data dict with element info
        """
        if not self.state.browser_data:
            self.state.browser_data = {"selections": {}, "prompt": ""}
        if "selections" not in self.state.browser_data:
            self.state.browser_data["selections"] = {}
        self.state.browser_data["selections"][selection_id] = data
        self._trigger_broadcast()

    def clear_browser_selections(self) -> None:
        """Clear all browser selections."""
        if self.state.browser_data:
            self.state.browser_data["selections"] = {}
        self._trigger_broadcast()

    def get_browser_data(self) -> tuple[dict[str, Any], str]:
        """Get current browser selections and prompt.

        Returns:
            Tuple of (selections dict, prompt string)
        """
        if not self.state.browser_data:
            return {}, ""
        return (
            dict(self.state.browser_data.get("selections", {})),
            self.state.browser_data.get("prompt", ""),
        )

    @property
    def event_count(self) -> int:
        """Total count of all CDP events stored across all connections.

        Uses cached counter from CDPSession for performance (no database query).
        """
        return sum(conn.cdp._event_count for conn in self.connections.values())

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
            self.state.registered_ports.add(port)

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

        if port not in self.state.registered_ports:
            return {"port": port, "removed": False}

        # Unwatch targets on this port
        targets_on_port = [tid for tid in list(self.connections.keys()) if parse_target(tid)[0] == port]
        if targets_on_port:
            self.unwatch_targets(targets_on_port)
        disconnected = targets_on_port

        # Remove port (inside lock)
        with self._state_lock:
            self.state.registered_ports.discard(port)

        self._trigger_broadcast()
        return {"port": port, "removed": True, "disconnected": disconnected}

    def list_ports(self) -> dict:
        """List registered ports with target/watched counts.

        Returns:
            {"ports": [{"port": N, "target_count": N, "watched_count": N, "status": str}]}
        """
        targets_result = self.list_targets()
        all_targets = targets_result.get("targets", [])

        port_stats: dict[int, dict] = {p: {"target_count": 0, "watched_count": 0} for p in self.state.registered_ports}

        for t in all_targets:
            port = t.get("chrome_port")
            if port in port_stats:
                port_stats[port]["target_count"] += 1
                if t.get("watched"):
                    port_stats[port]["watched_count"] += 1

        ports = [
            {"port": port, **stats, "status": "active" if stats["target_count"] > 0 else "reachable"}
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
        """Get active connection by target ID, with URL fallback.

        If exact target ID is not found, checks if the target was previously
        connected and a single live connection shares the same URL. This handles
        URL-watched targets (extension pages, service workers) that get new IDs
        on close/reopen.

        Args:
            target: Target ID in format "{port}:{short-id}"

        Returns:
            ActiveConnection if found (exact or unambiguous URL match), None otherwise
        """
        conn = self.connections.get(target)
        if conn:
            return conn

        # Fallback: check if old target had a URL, find single live match
        old_url = self._detached_urls.get(target)
        if not old_url:
            return None

        matches = [c for c in self.connections.values() if c.cdp.target_info.get("url") == old_url]
        if len(matches) == 1:
            return matches[0]

        return None

    def resolve_cdp(self, target: str) -> tuple[Any | None, dict]:
        """Resolve target ID to CDPSession for drill-down queries.

        Resolution order:
        1. Active connection by exact target ID
        2. Stashed DB via URL mapping (old target → URL → stashed CDPSession)
        3. Active connection via URL fallback (old target → URL → live connection)

        Args:
            target: Target ID (required — row IDs are per-DB and can collide)

        Returns:
            Tuple of (CDPSession or None, resolution_info dict).
            resolution_info has "via" key: "active", "stashed", or "url_fallback".
        """
        # 1. Active connection
        conn = self.connections.get(target)
        if conn:
            return conn.cdp, {"via": "active"}

        # 2-3. Old target ID → resolve via URL
        url = self._detached_urls.get(target)
        if not url:
            return None, {}

        # Prefer stashed DB (has the historical data for this target)
        if url in self._stashed_dbs:
            return self._stashed_dbs[url], {"via": "stashed", "url": url}

        # Fall back to live connection with same URL
        for c in self.connections.values():
            if c.cdp.target_info.get("url") == url:
                return c.cdp, {"via": "url_fallback", "url": url, "resolved_target": c.target}

        return None, {}

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

    def _register_body_capture_callback(self, cdp) -> None:
        """Register callback to capture response bodies on loadingFinished.

        Captures bodies immediately when requests complete, before page navigation
        can evict them from Chrome's memory. Bodies are stored in DuckDB as
        Network.responseBodyCaptured synthetic events.

        Only captures XHR, Fetch, and Document responses to avoid wasting time on
        assets (images, CSS, fonts) that would delay capturing critical API bodies.

        Uses ThreadPoolExecutor to avoid blocking WebSocket thread (which would
        cause ping/pong timeout). Pool is shared across all captures for efficiency.

        Args:
            cdp: CDPSession to register callback on
        """
        logger = logging.getLogger(__name__)

        # Resource types worth capturing (API responses, HTML)
        # Skip: Image, Stylesheet, Font, Media, Script (usually not needed for debugging)
        CAPTURE_TYPES = {"XHR", "Fetch", "Document"}

        # Cache requestId -> resourceType (populated by responseReceived, read by loadingFinished)
        # Dict lookup is O(1) and non-blocking - safe for WebSocket thread
        resource_types: dict[str, str] = {}

        # Shared executor - 4 workers handles typical page loads without overwhelming
        if not hasattr(self, "_body_capture_executor"):
            self._body_capture_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="body-capture")

        def capture_body(request_id: str, queued_at: float) -> None:
            """Capture body in thread pool worker."""
            import time

            started_at = time.time()
            delay_ms = int((started_at - queued_at) * 1000)

            try:
                result = cdp.execute("Network.getResponseBody", {"requestId": request_id}, timeout=5)
                elapsed_ms = int((time.time() - started_at) * 1000)

                if result and "body" in result:
                    cdp.store_response_body(
                        request_id,
                        result["body"],
                        result.get("base64Encoded", False),
                        capture_meta={"ok": True, "delay_ms": delay_ms, "elapsed_ms": elapsed_ms},
                    )
                else:
                    # No body in result (unusual)
                    cdp.store_response_body(
                        request_id,
                        "",
                        False,
                        capture_meta={"ok": False, "error": "empty", "delay_ms": delay_ms, "elapsed_ms": elapsed_ms},
                    )
            except Exception as e:
                elapsed_ms = int((time.time() - started_at) * 1000)
                error_msg = str(e)[:50]  # Truncate long errors
                cdp.store_response_body(
                    request_id,
                    "",
                    False,
                    capture_meta={"ok": False, "error": error_msg, "delay_ms": delay_ms, "elapsed_ms": elapsed_ms},
                )
            finally:
                # Clean up cache entry
                resource_types.pop(request_id, None)

        def on_response_received(event: dict) -> None:
            """Cache resource type for later lookup (non-blocking)."""
            params = event.get("params", {})
            request_id = params.get("requestId")
            resource_type = params.get("type")
            if request_id and resource_type:
                resource_types[request_id] = resource_type

        def on_loading_finished(event: dict) -> None:
            import time

            params = event.get("params", {})
            request_id = params.get("requestId")
            if not request_id:
                return

            # Check cached resource type (O(1) lookup, non-blocking)
            resource_type = resource_types.get(request_id)
            if not resource_type or resource_type not in CAPTURE_TYPES:
                resource_types.pop(request_id, None)  # Clean up
                return  # Skip assets

            # If Fetch capture already succeeded, skip (avoid duplicate capture)
            # But if Fetch failed/timed out (streaming), try as fallback
            if self.fetch.capture_enabled:
                capture_status = cdp.has_body_capture(request_id)
                if capture_status is True:
                    resource_types.pop(request_id, None)
                    return  # Already captured successfully by Fetch
                # capture_status is False (failed) or None (not attempted) - try fallback

            # Submit to thread pool - non-blocking, record queue time for latency tracking
            queued_at = time.time()
            self._body_capture_executor.submit(capture_body, request_id, queued_at)

        cdp.register_event_callback("Network.responseReceived", on_response_received)
        cdp.register_event_callback("Network.loadingFinished", on_loading_finished)
        logger.debug("Body capture callback registered (XHR, Fetch, Document only)")


__all__ = ["WebTapService"]
