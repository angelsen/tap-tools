"""Browser-level CDP session with WebSocket multiplexing.

PUBLIC API:
  - BrowserSession: Single WebSocket per Chrome port with session multiplexing
"""

import json
import logging
import threading
from concurrent.futures import Future, TimeoutError
from typing import Any

import httpx
import websocket

__all__ = ["BrowserSession"]

logger = logging.getLogger(__name__)


class BrowserSession:
    """Browser-level WebSocket connection with CDP session multiplexing.

    Owns a single WebSocket to /devtools/browser/<id> per Chrome debug port.
    Multiple CDPSessions can attach to targets through this browser connection.

    Attributes:
        port: Chrome debugging port.
    """

    def __init__(self, port: int = 9222):
        """Initialize browser session.

        Args:
            port: Chrome debugging port. Defaults to 9222.
        """
        self.port = port

        # WebSocket ownership
        self._ws_app: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._connected = threading.Event()

        # CDP request/response tracking
        self._next_id = 1
        self._pending: dict[int, Future] = {}
        self._lock = threading.Lock()

        # Session multiplexing
        self._sessions: dict[str, "Any"] = {}  # sessionId -> CDPSession (avoid circular import)

        # Dual-key watch state
        self._watched_targets: dict[str, dict] = {}  # target_id -> target_info (pages)
        self._watched_urls: dict[str, dict] = {}  # url -> target_info (ephemeral extension pages)

        # Target lifecycle callbacks (set by service)
        self._on_target_created: Any | None = None
        self._on_target_info_changed: Any | None = None
        self._on_sw_crashed: Any | None = None
        self._on_sw_reloaded: Any | None = None

    def connect(self) -> None:
        """Connect to browser WebSocket endpoint.

        Fetches browser WS URL from /json/version, connects WebSocket,
        calls Target.setDiscoverTargets(discover=true) for live events.

        Raises:
            RuntimeError: If already connected.
            TimeoutError: If connection fails within 5 seconds.
        """
        if self._ws_app:
            raise RuntimeError("Already connected")

        # Fetch browser WebSocket URL from /json/version
        try:
            resp = httpx.get(f"http://localhost:{self.port}/json/version", timeout=2)
            resp.raise_for_status()
            version_info = resp.json()
            ws_url = version_info.get("webSocketDebuggerUrl")
            if not ws_url:
                raise RuntimeError("No webSocketDebuggerUrl in /json/version")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch browser WS URL: {e}")

        # Create WebSocketApp with callbacks
        self._ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # Run in daemon thread
        self._ws_thread = threading.Thread(
            target=self._ws_app.run_forever,
            kwargs={
                "ping_interval": 120,
                "ping_timeout": 60,
                "skip_utf8_validation": True,
                "suppress_origin": True,
            },
        )
        self._ws_thread.daemon = True
        self._ws_thread.start()

        # Wait for connection
        if not self._connected.wait(timeout=5):
            self.disconnect()
            raise TimeoutError("Failed to connect to browser WebSocket")

        # Enable target discovery for lifecycle events
        try:
            self.execute("Target.setDiscoverTargets", {"discover": True})
        except Exception as e:
            logger.warning(f"Failed to enable target discovery: {e}")

    def disconnect(self) -> None:
        """Close browser WebSocket. All attached sessions become invalid."""
        with self._lock:
            ws_app = self._ws_app
            self._ws_app = None

        if ws_app:
            ws_app.close()

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=2)
            self._ws_thread = None

        self._connected.clear()

    def attach(self, target_id: str) -> str:
        """Attach to target and return sessionId.

        Args:
            target_id: CDP target ID to attach to.

        Returns:
            Session ID for this attached target.

        Raises:
            RuntimeError: If not connected or attach fails.
        """
        result = self.execute("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        return result["sessionId"]

    def detach(self, session_id: str) -> None:
        """Detach from target session.

        Args:
            session_id: Session ID to detach from.
        """
        try:
            self.execute("Target.detachFromTarget", {"sessionId": session_id})
        except Exception as e:
            logger.debug(f"Error detaching session {session_id}: {e}")

    def send(self, method: str, params: dict | None = None, session_id: str | None = None) -> Future:
        """Send CDP command asynchronously.

        Args:
            method: CDP method name.
            params: Optional command parameters.
            session_id: Optional session ID for routing to specific target.

        Returns:
            Future containing CDP response 'result' field.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._ws_app:
            raise RuntimeError("Not connected")

        with self._lock:
            msg_id = self._next_id
            self._next_id += 1

            future = Future()
            self._pending[msg_id] = future

        # Build CDP message
        message = {"id": msg_id, "method": method}
        if params:
            message["params"] = params
        if session_id:
            message["sessionId"] = session_id

        self._ws_app.send(json.dumps(message))

        return future

    def execute(
        self, method: str, params: dict | None = None, session_id: str | None = None, timeout: float = 30
    ) -> Any:
        """Send CDP command synchronously.

        Args:
            method: CDP method name.
            params: Optional command parameters.
            session_id: Optional session ID for routing to specific target.
            timeout: Command timeout in seconds.

        Returns:
            CDP response 'result' field.

        Raises:
            TimeoutError: If command times out.
            RuntimeError: If CDP returns error.
        """
        future = self.send(method, params, session_id)

        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            raise TimeoutError(f"Command {method} timed out")

    def register_session(self, session_id: str, cdp_session: "Any") -> bool:
        """Register CDPSession for event routing. No-op if already registered.

        Args:
            session_id: Session ID returned from attach.
            cdp_session: CDPSession instance to route events to.

        Returns:
            True if registered, False if session_id already existed.
        """
        with self._lock:
            if session_id in self._sessions:
                return False
            self._sessions[session_id] = cdp_session
            return True

    def unregister_session(self, session_id: str) -> None:
        """Unregister CDPSession.

        Args:
            session_id: Session ID to unregister.
        """
        with self._lock:
            self._sessions.pop(session_id, None)

    def get_session(self, session_id: str) -> "Any | None":
        """Get CDPSession by session ID (thread-safe).

        Args:
            session_id: Session ID to look up.

        Returns:
            CDPSession if registered, None otherwise.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def watch_target(self, target_id: str, target_info: dict) -> None:
        """Add target to watched set (thread-safe).

        Args:
            target_id: Target ID in format "{port}:{short-id}".
            target_info: Target info dict from Chrome.
        """
        with self._lock:
            self._watched_targets[target_id] = target_info

    def watch_url(self, url: str, target_info: dict) -> None:
        """Add URL to watched set for ephemeral targets (thread-safe).

        Args:
            url: URL to watch (e.g., chrome-extension:// page).
            target_info: Target info dict from Chrome.
        """
        with self._lock:
            self._watched_urls[url] = target_info

    def unwatch_target(self, target_id: str) -> dict | None:
        """Remove target from watched set (thread-safe).

        Args:
            target_id: Target ID to unwatch.

        Returns:
            Removed target info, or None if not watched.
        """
        with self._lock:
            return self._watched_targets.pop(target_id, None)

    def unwatch_url(self, url: str) -> dict | None:
        """Remove URL from watched set (thread-safe).

        Args:
            url: URL to unwatch.

        Returns:
            Removed target info, or None if not watched.
        """
        with self._lock:
            return self._watched_urls.pop(url, None)

    def is_watched(self, target_id: str, url: str = "") -> bool:
        """Check if target or URL is watched (thread-safe).

        Args:
            target_id: Target ID to check.
            url: Optional URL to also check.

        Returns:
            True if target_id or url is in watched sets.
        """
        with self._lock:
            if target_id in self._watched_targets:
                return True
            return bool(url and url in self._watched_urls)

    def get_watched_snapshot(self) -> tuple[list[str], list[str]]:
        """Get snapshot of watched target IDs and URLs (thread-safe).

        Returns plain lists safe to iterate from any thread.

        Returns:
            Tuple of (watched_target_ids, watched_urls).
        """
        with self._lock:
            return list(self._watched_targets.keys()), list(self._watched_urls.keys())

    def clear_all_watches(self) -> tuple[list[str], list[str]]:
        """Clear all watches and return what was cleared (thread-safe).

        Returns:
            Tuple of (cleared_target_ids, cleared_urls).
        """
        with self._lock:
            target_ids = list(self._watched_targets.keys())
            urls = list(self._watched_urls.keys())
            self._watched_targets.clear()
            self._watched_urls.clear()
            return target_ids, urls

    def list_all_targets(self) -> list[dict]:
        """Get all targets via CDP Target.getTargets.

        Returns:
            List of TargetInfo dicts with 'targetId' field.
        """
        result = self.execute("Target.getTargets")
        return result.get("targetInfos", [])

    def set_target_lifecycle_callbacks(self, on_created, on_info_changed, on_sw_crashed, on_sw_reloaded) -> None:
        """Set callbacks for target lifecycle events. Called by service."""
        self._on_target_created = on_created
        self._on_target_info_changed = on_info_changed
        self._on_sw_crashed = on_sw_crashed
        self._on_sw_reloaded = on_sw_reloaded

    def _resolve_watched_target(self, target_info: dict) -> str | None:
        """Match a targetInfo to a watched target.

        Resolution order: target_id → URL → opener (popup from watched tab).
        """
        from webtap.targets import make_target

        target_id = make_target(self.port, target_info.get("targetId", ""))

        with self._lock:
            # Direct target_id match (pages, non-extension targets)
            if target_id in self._watched_targets:
                return target_id

            # URL match for ephemeral extension pages
            url = target_info.get("url", "")
            if url and url in self._watched_urls:
                return target_id  # return NEW target_id, not stored one

            # Opener match — popup opened by a watched tab
            opener_id = target_info.get("openerId", "")
            if opener_id:
                opener_target = make_target(self.port, opener_id)
                if opener_target in self._watched_targets:
                    return target_id

        return None

    @property
    def is_connected(self) -> bool:
        """Check if browser WebSocket is connected.

        Returns:
            True if connected to browser endpoint.
        """
        return self._connected.is_set()

    def _fire_callback(self, callback, args: tuple, name: str) -> None:
        """Run callback off WebSocket thread."""
        threading.Thread(target=callback, args=args, daemon=True, name=name).start()

    def _on_open(self, ws):
        """WebSocket connection established."""
        logger.info(f"Browser WebSocket connected (port {self.port})")
        self._connected.set()

    def _on_message(self, ws, message):
        """Route messages to appropriate handlers.

        Routes by:
        - Has 'id': Command response → resolve Future
        - Has 'sessionId' + 'method': Session event → CDPSession._handle_event()
        - Has 'method' only: Browser-level event → _handle_browser_event()
        """
        try:
            data = json.loads(message)

            # Command response
            if "id" in data:
                with self._lock:
                    future = self._pending.pop(data["id"], None)

                if future:
                    if "error" in data:
                        future.set_exception(RuntimeError(data["error"]))
                    else:
                        future.set_result(data.get("result", {}))

            # CDP event
            elif "method" in data:
                session_id = data.get("sessionId")
                if session_id:
                    # Session-scoped event -- intercept SW lifecycle before CDPSession
                    event_method = data.get("method", "")

                    if event_method == "Inspector.targetCrashed":
                        if self._on_sw_crashed:
                            self._on_sw_crashed(session_id)
                        return

                    if event_method == "Inspector.targetReloadedAfterCrash":
                        if self._on_sw_reloaded:
                            # Run off WS thread -- handler calls execute() for domain re-enables
                            self._fire_callback(self._on_sw_reloaded, (session_id,), f"sw-reloaded-{session_id[:8]}")
                        return

                    # Normal session event - route to CDPSession
                    with self._lock:
                        cdp_session = self._sessions.get(session_id)
                    if cdp_session:
                        cdp_session._handle_event(data)
                else:
                    # Browser-level event
                    self._handle_browser_event(data)

        except Exception as e:
            logger.error(f"Error handling browser message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"Browser WebSocket error: {error}")

    def _on_close(self, ws, code, reason):
        """Handle WebSocket closure and cleanup."""
        logger.info(f"Browser WebSocket closed: code={code} reason={reason}")

        # Mark as disconnected
        was_connected = self._connected.is_set()
        self._connected.clear()

        # Fail all pending futures
        with self._lock:
            ws_app_was_set = self._ws_app is not None
            self._ws_app = None

            for future in self._pending.values():
                future.set_exception(RuntimeError(f"Browser connection closed: {reason or 'Unknown'}"))
            self._pending.clear()

            # Copy sessions list before notifying (avoid modification during iteration)
            sessions_to_notify = list(self._sessions.items())

        # Notify all registered sessions of disconnect (if unexpected)
        if was_connected and ws_app_was_set:
            for session_id, cdp_session in sessions_to_notify:
                if cdp_session._disconnect_callback:
                    try:
                        self._fire_callback(
                            cdp_session._disconnect_callback, (code, reason), f"browser-disconnect-{session_id[:8]}"
                        )
                    except Exception as e:
                        logger.error(f"Error calling disconnect callback for {session_id}: {e}")

    def _handle_browser_event(self, data: dict) -> None:
        """Handle browser-level CDP events.

        Handles:
        - Target.targetCreated: Trigger attach for watched/opener-matched targets
        - Target.targetDestroyed: Clean up, trigger disconnect callback
        - Target.targetInfoChanged: Update metadata via callback
        - Target.detachedFromTarget: Unregister session, notify service

        Args:
            data: CDP event dictionary.
        """
        method = data.get("method")
        params = data.get("params", {})

        if method == "Target.targetCreated":
            target_info = params.get("targetInfo", {})
            # Check if target matches a watch — trigger re-attach
            target_id = self._resolve_watched_target(target_info)
            if target_id and self._on_target_created:
                self._on_target_created(target_info, target_id)

        elif method == "Target.targetDestroyed":
            target_id_chrome = params.get("targetId")
            if not target_id_chrome:
                return
            # Find and notify session for this target
            with self._lock:
                sessions_to_notify = [
                    (sid, sess) for sid, sess in self._sessions.items() if sess.chrome_target_id == target_id_chrome
                ]
            for session_id, cdp_session in sessions_to_notify:
                if cdp_session._disconnect_callback:
                    self._fire_callback(
                        cdp_session._disconnect_callback,
                        (1001, "Target destroyed"),
                        f"target-destroyed-{session_id[:8]}",
                    )

        elif method == "Target.targetInfoChanged":
            target_info = params.get("targetInfo", {})

            # URL may now match a watch (targetCreated had empty URL)
            chrome_target_id = target_info.get("targetId", "")
            already_attached = False
            with self._lock:
                already_attached = any(sess.chrome_target_id == chrome_target_id for sess in self._sessions.values())
            if not already_attached:
                target_id = self._resolve_watched_target(target_info)
                if target_id and self._on_target_created:
                    self._on_target_created(target_info, target_id)

            # Always update metadata on connected targets
            if self._on_target_info_changed:
                self._on_target_info_changed(target_info)

        elif method == "Target.detachedFromTarget":
            session_id = params.get("sessionId")
            if session_id:
                with self._lock:
                    cdp = self._sessions.get(session_id)
                if cdp:
                    self.unregister_session(session_id)
                    if cdp._disconnect_callback:
                        self._fire_callback(
                            cdp._disconnect_callback, (1001, "Target detached"), f"target-detached-{session_id[:8]}"
                        )
