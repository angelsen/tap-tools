"""CDP Session with native event storage.

PUBLIC API:
  - CDPSession: WebSocket-based CDP client with DuckDB event storage
"""

import json
import logging
import queue
import threading
from concurrent.futures import Future, TimeoutError
from typing import Any

import duckdb
import httpx
import websocket

from webtap.cdp.har import _create_har_views

__all__ = ["CDPSession"]

logger = logging.getLogger(__name__)

# Event storage limits
MAX_EVENTS = 50_000  # FIFO eviction threshold
PRUNE_BATCH_SIZE = 5_000  # Delete in batches for efficiency
PRUNE_CHECK_INTERVAL = 1_000  # Check count every N events


class CDPSession:
    """WebSocket-based CDP client with native event storage.

    Stores CDP events as-is in DuckDB for minimal overhead and maximum flexibility.
    Provides field discovery and query capabilities for dynamic data exploration.

    Attributes:
        port: Chrome debugging port.
        timeout: Default timeout for execute() calls.
        db: DuckDB connection for event storage.
    """

    def __init__(self, port: int = 9222, timeout: float = 30):
        """Initialize CDP session with WebSocket and DuckDB storage.

        Args:
            port: Chrome debugging port. Defaults to 9222.
            timeout: Default timeout for execute() calls. Defaults to 30.
        """
        self.port = port
        self.timeout = timeout

        # WebSocketApp instance
        self.ws_app: websocket.WebSocketApp | None = None
        self.ws_thread: threading.Thread | None = None

        # Connection state
        self.connected = threading.Event()
        self.page_info: dict | None = None

        # Target tracking for multi-target support
        self.target: str | None = None

        # CDP request/response tracking
        self._next_id = 1
        self._pending: dict[int, Future] = {}
        self._lock = threading.Lock()

        # DuckDB storage - store events AS-IS
        # DuckDB connections are NOT thread-safe - use dedicated DB thread
        self.db = duckdb.connect(":memory:")
        self._db_work_queue: queue.Queue = queue.Queue()
        self._db_result_queues: dict[int, queue.Queue] = {}
        self._db_running = True

        # Start dedicated database thread
        self._db_thread = threading.Thread(target=self._db_worker, daemon=True)
        self._db_thread.start()

        # Initialize schema with indexed columns for fast filtering
        # Must wait for table to exist before any queries can run
        self._db_execute(
            """CREATE TABLE IF NOT EXISTS events (
                event JSON,
                method VARCHAR,
                target VARCHAR,
                request_id VARCHAR
            )""",
            wait_result=True,
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_events_method ON events(method)",
            wait_result=True,
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_events_target ON events(target)",
            wait_result=True,
        )
        self._db_execute(
            "CREATE INDEX IF NOT EXISTS idx_events_request_id ON events(request_id)",
            wait_result=True,
        )

        # Create HAR views for aggregated network request data
        _create_har_views(self._db_execute)

        # Event count for pruning (approximate, updated periodically)
        self._event_count = 0

        # Paused request count (incremented on Fetch.requestPaused, decremented on resolution)
        self._paused_count = 0

        # Event callbacks for real-time handling
        # Maps event method (e.g. "Overlay.inspectNodeRequested") to list of callbacks
        self._event_callbacks: dict[str, list] = {}

        # Broadcast callback for SSE state updates (set by service)
        self._broadcast_callback: "Any | None" = None

        # Disconnect callback for service-level cleanup
        self._disconnect_callback: "Any | None" = None

    # Event method prefixes that affect displayed state (trigger SSE broadcast)
    _STATE_AFFECTING_PREFIXES = (
        "Network.",  # Network requests table
        "Fetch.",  # Fetch interception
        "Runtime.consoleAPI",  # Console messages
        "Overlay.",  # DOM inspection
        "DOM.",  # DOM changes
    )

    def _is_state_affecting_event(self, method: str) -> bool:
        """Check if an event method affects displayed state.

        Only state-affecting events trigger SSE broadcasts to reduce latency
        from noisy CDP events (like Page.frameNavigated, Target.*, etc.)
        """
        return method.startswith(self._STATE_AFFECTING_PREFIXES)

    def _extract_request_id(self, data: dict) -> str | None:
        """Extract requestId from CDP event params for indexing."""
        return data.get("params", {}).get("requestId")

    def _db_worker(self) -> None:
        """Dedicated thread for all database operations.

        Ensures thread safety by serializing all DuckDB access through one thread.
        DuckDB connections are not thread-safe - sharing them causes malloc corruption.
        """
        while self._db_running:
            try:
                task = self._db_work_queue.get(timeout=1)

                if task is None:  # Shutdown signal
                    break

                operation_type, sql, params, result_queue_id = task

                try:
                    if operation_type == "execute":
                        result = self.db.execute(sql, params or [])
                        data = result.fetchall() if result else []
                    elif operation_type == "delete":
                        self.db.execute(sql, params or [])
                        data = None
                    else:
                        data = None

                    # Send result back if requested
                    if result_queue_id and result_queue_id in self._db_result_queues:
                        self._db_result_queues[result_queue_id].put(("success", data))

                except Exception as e:
                    logger.error(f"Database error: {e}")
                    if result_queue_id and result_queue_id in self._db_result_queues:
                        self._db_result_queues[result_queue_id].put(("error", str(e)))

                finally:
                    self._db_work_queue.task_done()

            except queue.Empty:
                continue

    def _db_execute(self, sql: str, params: list | None = None, wait_result: bool = True) -> Any:
        """Submit database operation to dedicated thread.

        Args:
            sql: SQL query or command
            params: Optional query parameters
            wait_result: Block until operation completes and return result

        Returns:
            Query results if wait_result=True, None otherwise

        Raises:
            TimeoutError: If operation takes longer than 30 seconds
            RuntimeError: If database operation fails
        """
        result_queue_id = None
        result_queue = None

        try:
            if wait_result:
                result_queue_id = id(threading.current_thread())
                result_queue = queue.Queue()
                self._db_result_queues[result_queue_id] = result_queue

            # Submit to work queue
            self._db_work_queue.put(("execute", sql, params, result_queue_id))

            if wait_result and result_queue and result_queue_id:
                try:
                    status, data = result_queue.get(timeout=30)
                except queue.Empty:
                    raise TimeoutError(f"Database operation timed out: {sql[:50]}...")

                if status == "error":
                    raise RuntimeError(f"Database error: {data}")
                return data

            return None
        finally:
            # Always clean up result queue entry to prevent leaks
            if result_queue_id and result_queue_id in self._db_result_queues:
                del self._db_result_queues[result_queue_id]

    def list_pages(self) -> list[dict]:
        """List available Chrome pages via HTTP API.

        Returns:
            List of page dictionaries with webSocketDebuggerUrl.
        """
        try:
            resp = httpx.get(f"http://localhost:{self.port}/json", timeout=2)
            resp.raise_for_status()
            pages = resp.json()
            return [p for p in pages if p.get("type") == "page" and "webSocketDebuggerUrl" in p]
        except Exception as e:
            logger.error(f"Failed to list pages: {e}")
            return []

    def connect(
        self,
        page_index: int | None = None,
        page_id: str | None = None,
        page_info: dict | None = None,
    ) -> None:
        """Connect to Chrome page via WebSocket.

        Establishes WebSocket connection and starts event collection.
        Does not auto-enable CDP domains - use execute() for that.

        Args:
            page_index: Index of page to connect to. Defaults to 0.
            page_id: Stable page ID across tab reordering.
            page_info: Pre-resolved page dict with webSocketDebuggerUrl (avoids HTTP call).

        Raises:
            RuntimeError: If already connected or no pages available.
            ValueError: If page_id not found.
            IndexError: If page_index out of range.
            TimeoutError: If connection fails within 5 seconds.
        """
        if self.ws_app:
            raise RuntimeError("Already connected")

        # Use provided page_info directly if available (avoids duplicate list_pages call)
        if page_info and "webSocketDebuggerUrl" in page_info:
            page = page_info
        else:
            pages = self.list_pages()
            if not pages:
                raise RuntimeError("No pages available")

            # Find the page by ID or index
            if page_id:
                page = next((p for p in pages if p.get("id") == page_id), None)
                if not page:
                    raise ValueError(f"Page with ID {page_id} not found")
            elif page_index is not None:
                if page_index >= len(pages):
                    raise IndexError(f"Page {page_index} out of range")
                page = pages[page_index]
            else:
                # Default to first page
                page = pages[0]

        ws_url = page["webSocketDebuggerUrl"]
        self.page_info = page

        # Create WebSocketApp with callbacks
        self.ws_app = websocket.WebSocketApp(
            ws_url, on_open=self._on_open, on_message=self._on_message, on_error=self._on_error, on_close=self._on_close
        )

        # Let WebSocketApp handle everything in a thread
        self.ws_thread = threading.Thread(
            target=self.ws_app.run_forever,
            kwargs={
                "ping_interval": 120,  # Ping every 2 min
                "ping_timeout": 60,  # Wait 60s for pong (handles heavy page loads)
                # No auto-reconnect - make disconnects explicit
                "skip_utf8_validation": True,  # Faster
                "suppress_origin": True,  # Required for Android Chrome (rejects localhost origin)
            },
        )
        self.ws_thread.daemon = True
        self.ws_thread.start()

        # Wait for connection
        if not self.connected.wait(timeout=5):
            self.disconnect()
            raise TimeoutError("Failed to connect to Chrome")

    def disconnect(self) -> None:
        """Disconnect WebSocket while preserving events and DB thread.

        Events and DB thread persist across connection cycles.
        Use cleanup() on app exit to shutdown DB thread.
        """
        # Atomically clear ws_app to signal manual disconnect
        # This prevents _on_close from triggering service callback
        with self._lock:
            ws_app = self.ws_app
            self.ws_app = None

        if ws_app:
            ws_app.close()

        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=2)
            self.ws_thread = None

        # Keep DB thread running - events preserved for reconnection
        # DB cleanup happens in cleanup() on app exit only

        self.connected.clear()
        self.page_info = None
        self.target = None

    def decrement_paused_count(self) -> None:
        """Decrement paused request counter (called when request is resumed/failed/fulfilled)."""
        if self._paused_count > 0:
            self._paused_count -= 1

    def cleanup(self) -> None:
        """Shutdown DB thread and disconnect (call on app exit only).

        This is the only place where DB thread should be stopped.
        Events are lost when DB thread stops (in-memory database).
        """
        # Disconnect WebSocket if connected
        if self.ws_app:
            self.disconnect()

        # Shutdown database thread
        self._db_running = False
        self._db_work_queue.put(None)  # Signal shutdown
        if self._db_thread.is_alive():
            self._db_thread.join(timeout=2)

    def send(self, method: str, params: dict | None = None) -> Future:
        """Send CDP command asynchronously.

        Args:
            method: CDP method like "Page.navigate" or "Network.enable".
            params: Optional command parameters.

        Returns:
            Future containing CDP response 'result' field.

        Raises:
            RuntimeError: If not connected to Chrome.
        """
        if not self.ws_app:
            raise RuntimeError("Not connected")

        with self._lock:
            msg_id = self._next_id
            self._next_id += 1

            future = Future()
            self._pending[msg_id] = future

        # Send CDP command
        message = {"id": msg_id, "method": method}
        if params:
            message["params"] = params

        self.ws_app.send(json.dumps(message))

        return future

    def execute(self, method: str, params: dict | None = None, timeout: float | None = None) -> Any:
        """Send CDP command synchronously.

        Args:
            method: CDP method like "Page.navigate" or "Network.enable".
            params: Optional command parameters.
            timeout: Override default timeout.

        Returns:
            CDP response 'result' field.

        Raises:
            TimeoutError: If command times out.
            RuntimeError: If CDP returns error or not connected.
        """
        future = self.send(method, params)

        try:
            return future.result(timeout=timeout or self.timeout)
        except TimeoutError:
            # Clean up the pending future
            with self._lock:
                for msg_id, f in list(self._pending.items()):
                    if f is future:
                        self._pending.pop(msg_id, None)
                        break
            raise TimeoutError(f"Command {method} timed out")

    def _on_open(self, ws):
        """WebSocket connection established."""
        logger.info("WebSocket connected")
        self.connected.set()

    def _on_message(self, ws, message):
        """Handle CDP messages - store events as-is, resolve command futures."""
        try:
            data = json.loads(message)

            # Command response - resolve future
            if "id" in data:
                msg_id = data["id"]
                with self._lock:
                    future = self._pending.pop(msg_id, None)

                if future:
                    if "error" in data:
                        future.set_exception(RuntimeError(data["error"]))
                    else:
                        future.set_result(data.get("result", {}))

            # CDP event - store AS-IS in DuckDB with request_id for fast lookups
            elif "method" in data:
                method = data.get("method", "")
                request_id = self._extract_request_id(data)
                self._db_execute(
                    "INSERT INTO events (event, method, target, request_id) VALUES (?, ?, ?, ?)",
                    [json.dumps(data), method, self.target, request_id],
                    wait_result=False,
                )
                self._event_count += 1

                # Track paused request count for fast access
                if method == "Fetch.requestPaused":
                    self._paused_count += 1

                # Prune old events periodically to prevent unbounded growth
                if self._event_count % PRUNE_CHECK_INTERVAL == 0:
                    self._maybe_prune_events()

                # Call registered event callbacks
                self._dispatch_event_callbacks(data)

                # Trigger SSE broadcast only for state-affecting events
                # Skip noisy events that don't affect displayed state
                if self._is_state_affecting_event(method):
                    self._trigger_state_broadcast()

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, code, reason):
        """Handle WebSocket closure and cleanup."""
        logger.info(f"WebSocket closed: code={code} reason={reason}")

        # Mark as disconnected
        was_connected = self.connected.is_set()
        self.connected.clear()

        # Fail pending commands and check if this is unexpected disconnect
        is_unexpected = False
        with self._lock:
            # Capture and clear ws_app FIRST to prevent new sends from adding futures
            ws_app_was_set = self.ws_app is not None
            self.ws_app = None

            # Now safe to clear pending - no new futures can be added
            for future in self._pending.values():
                future.set_exception(RuntimeError(f"Connection closed: {reason or 'Unknown'}"))
            self._pending.clear()

            # Unexpected disconnect: was connected and ws_app was set (not manual disconnect)
            is_unexpected = was_connected and ws_app_was_set
            self.page_info = None
            self.target = None

        # Trigger service-level cleanup if this was unexpected
        if is_unexpected and self._disconnect_callback:
            try:
                # Call in background to avoid blocking WebSocket thread
                threading.Thread(
                    target=self._disconnect_callback, args=(code, reason), daemon=True, name="cdp-disconnect-handler"
                ).start()
            except Exception as e:
                logger.error(f"Error calling disconnect callback: {e}")

        # Trigger SSE broadcast immediately
        self._trigger_state_broadcast()

    def _maybe_prune_events(self) -> None:
        """Prune oldest events if count exceeds MAX_EVENTS.

        Uses FIFO deletion - removes oldest events first (by rowid).
        Non-blocking: queues delete operation to DB thread.
        """
        if self._event_count <= MAX_EVENTS:
            return

        excess = self._event_count - MAX_EVENTS
        # Delete in batches, but at least the excess
        delete_count = max(excess, PRUNE_BATCH_SIZE)

        self._db_execute(
            "DELETE FROM events WHERE rowid IN (SELECT rowid FROM events ORDER BY rowid LIMIT ?)",
            [delete_count],
            wait_result=False,
        )

        self._event_count -= delete_count
        logger.debug(f"Pruned {delete_count} old events, ~{self._event_count} remaining")

    def clear_events(self) -> None:
        """Clear all stored events."""
        self._db_execute("DELETE FROM events", wait_result=False)
        self._event_count = 0

    def query(self, sql: str, params: list | None = None) -> list:
        """Query stored CDP events using DuckDB SQL.

        Events are stored in 'events' table with single JSON 'event' column.
        Use json_extract_string() for accessing nested fields.

        Args:
            sql: DuckDB SQL query string.
            params: Optional query parameters.

        Returns:
            List of result rows.

        Examples:
            query("SELECT * FROM events WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'")
            query("SELECT json_extract_string(event, '$.params.request.url') as url FROM events")
        """
        return self._db_execute(sql, params)

    def fetch_body(self, request_id: str) -> dict:
        """Fetch response body - checks captured bodies first, then CDP fallback.

        When capture mode is enabled, bodies are stored in DuckDB as
        Network.responseBodyCaptured events. This method checks there first,
        falling back to Network.getResponseBody CDP call if not found.

        Args:
            request_id: Network request ID from CDP events.

        Returns:
            Dict with either:
            - {"body": str, "base64Encoded": bool, "capture": {...}} on success
            - {"error": str, "capture": {...}} on capture failure
            - {"error": str} on CDP fallback failure
        """
        # First check for captured body in DuckDB
        try:
            rows = self._db_execute(
                """
                SELECT json_extract_string(event, '$.params.body') as body,
                       json_extract(event, '$.params.base64Encoded') as base64_encoded,
                       json_extract(event, '$.params.capture') as capture
                FROM events
                WHERE method = 'Network.responseBodyCaptured'
                  AND request_id = ?
                LIMIT 1
                """,
                [request_id],
            )
            if rows:
                body, base64_encoded, capture_json = rows[0]
                capture = json.loads(capture_json) if capture_json else None

                # Check if capture failed
                if capture and not capture.get("ok"):
                    error_msg = capture.get("error", "capture failed")
                    return {"error": error_msg, "capture": capture}

                result: dict = {"body": body, "base64Encoded": base64_encoded == "true"}
                if capture:
                    result["capture"] = capture
                return result
        except Exception as e:
            logger.debug(f"Error checking captured body for {request_id}: {e}")

        # Fall back to lazy CDP lookup
        try:
            return self.execute("Network.getResponseBody", {"requestId": request_id})
        except Exception as e:
            error_msg = str(e)
            logger.debug(f"Failed to fetch body for {request_id}: {error_msg}")
            return {"error": error_msg}

    def store_response_body(
        self,
        request_id: str,
        body: str,
        base64_encoded: bool = False,
        capture_meta: dict | None = None,
    ) -> None:
        """Store captured response body with optional capture metadata.

        Args:
            request_id: CDP request ID
            body: Response body (base64 or raw)
            base64_encoded: Whether body is base64 encoded
            capture_meta: Optional capture metadata (ok, error, delay_ms, elapsed_ms)
        """
        params: dict = {
            "requestId": request_id,
            "body": body,
            "base64Encoded": base64_encoded,
        }
        if capture_meta:
            params["capture"] = capture_meta

        event = {"method": "Network.responseBodyCaptured", "params": params}
        event_json = json.dumps(event)
        self._db_execute(
            "INSERT INTO events (event, method, target, request_id) VALUES (?, ?, ?, ?)",
            [event_json, event["method"], self.target, request_id],
            wait_result=False,
        )

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket connection is active.

        Returns:
            True if connected to Chrome page.
        """
        return self.connected.is_set()

    def set_disconnect_callback(self, callback) -> None:
        """Register callback for unexpected disconnect events.

        Called when WebSocket closes externally (tab close, crash, etc).
        NOT called on manual disconnect() to avoid duplicate cleanup.

        Args:
            callback: Function called with (code: int, reason: str)
        """
        self._disconnect_callback = callback
        logger.debug("Disconnect callback registered")

    def register_event_callback(self, method: str, callback) -> None:
        """Register callback for specific CDP event.

        Args:
            method: CDP event method (e.g. "Overlay.inspectNodeRequested")
            callback: Async function called with event data dict

        Example:
            async def on_inspect(event):
                node_id = event.get("params", {}).get("backendNodeId")
                print(f"User clicked node: {node_id}")

            cdp.register_event_callback("Overlay.inspectNodeRequested", on_inspect)
        """
        if method not in self._event_callbacks:
            self._event_callbacks[method] = []
        # Prevent duplicate registrations (defense in depth)
        if callback not in self._event_callbacks[method]:
            self._event_callbacks[method].append(callback)
            logger.debug(f"Registered callback for {method}")

    def unregister_event_callback(self, method: str, callback) -> None:
        """Unregister event callback.

        Args:
            method: CDP event method
            callback: Callback function to remove
        """
        if method in self._event_callbacks:
            try:
                self._event_callbacks[method].remove(callback)
                logger.debug(f"Unregistered callback for {method}")
            except ValueError:
                pass

    def _dispatch_event_callbacks(self, event: dict) -> None:
        """Dispatch event to registered callbacks.

        All callbacks must be synchronous and should return quickly.
        Failed callbacks are logged but not retried - WebSocket reconnection
        is handled by websocket-client library automatically.

        Args:
            event: CDP event dictionary with 'method' and 'params'
        """
        method = event.get("method")
        if not method or method not in self._event_callbacks:
            return

        # Call all registered callbacks (must be sync)
        for callback in self._event_callbacks[method]:
            try:
                callback(event)
            except TimeoutError:
                logger.warning(f"{method} callback timed out - page may be busy, user can retry")
            except Exception as e:
                logger.error(f"Error in {method} callback: {e}")

    def set_broadcast_callback(self, callback: "Any") -> None:
        """Set callback for broadcasting state changes.

        Service owns coalescing - CDPSession just signals that state changed.

        Args:
            callback: Function to call when state changes (service._trigger_broadcast)
        """
        self._broadcast_callback = callback
        logger.debug("Broadcast callback set on CDPSession")

    def _trigger_state_broadcast(self) -> None:
        """Signal that state changed (service handles coalescing).

        Called after CDP events. Service decides whether to actually broadcast.
        """
        if self._broadcast_callback:
            try:
                self._broadcast_callback()
            except Exception as e:
                logger.debug(f"Failed to trigger broadcast: {e}")
