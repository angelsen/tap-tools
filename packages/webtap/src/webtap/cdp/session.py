"""CDP Session with native event storage.

PUBLIC API:
  - CDPSession: Session-multiplexed CDP client with DuckDB event storage
"""

import json
import logging
import queue
import threading
from concurrent.futures import Future, TimeoutError
from typing import Any, TYPE_CHECKING

import duckdb

from webtap.cdp.har import _create_har_views

if TYPE_CHECKING:
    from webtap.cdp.browser import BrowserSession

__all__ = ["CDPSession"]

logger = logging.getLogger(__name__)

# Event storage limits
MAX_EVENTS = 50_000  # FIFO eviction threshold
PRUNE_BATCH_SIZE = 5_000  # Delete in batches for efficiency
PRUNE_CHECK_INTERVAL = 1_000  # Check count every N events


class CDPSession:
    """Session-multiplexed CDP client with native event storage.

    Routes commands through BrowserSession WebSocket. Stores CDP events
    as-is in DuckDB for minimal overhead and maximum flexibility.

    Attributes:
        port: Chrome debugging port.
        timeout: Default timeout for execute() calls.
        db: DuckDB connection for event storage.
        target: Target ID for this session.
        target_info: Full targetInfo from Target.getTargets().
    """

    def __init__(self, browser: "BrowserSession", session_id: str, target_info: dict, port: int, timeout: float = 30):
        """Initialize CDP session bound to BrowserSession.

        Args:
            browser: BrowserSession to route commands through.
            session_id: Session ID from Target.attachToTarget.
            target_info: Full targetInfo dictionary from Target.getTargets().
            port: Chrome debugging port.
            timeout: Default timeout for execute() calls. Defaults to 30.
        """
        self._browser = browser
        self._session_id = session_id
        self.target_info = target_info
        self.chrome_target_id = target_info.get("id") or target_info.get("targetId", "")
        self.port = port
        self.timeout = timeout

        # Target tracking (set by service after registration)
        self.target: str | None = None

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

    def disconnect(self) -> None:
        """Detach from browser session.

        Preserves events and DB thread. Use cleanup() on app exit to shutdown DB thread.
        """
        self._browser.detach(self._session_id)
        self._browser.unregister_session(self._session_id)
        self.target = None

    def decrement_paused_count(self) -> None:
        """Decrement paused request counter (called when request is resumed/failed/fulfilled)."""
        if self._paused_count > 0:
            self._paused_count -= 1

    def cleanup(self) -> None:
        """Shutdown DB thread (call on app exit only).

        This is the only place where DB thread should be stopped.
        Events are lost when DB thread stops (in-memory database).
        """
        # Shutdown database thread
        self._db_running = False
        self._db_work_queue.put(None)  # Signal shutdown
        if self._db_thread.is_alive():
            self._db_thread.join(timeout=2)

    def send(self, method: str, params: dict | None = None) -> Future:
        """Send CDP command asynchronously via BrowserSession.

        Args:
            method: CDP method like "Page.navigate" or "Network.enable".
            params: Optional command parameters.

        Returns:
            Future containing CDP response 'result' field.

        Raises:
            RuntimeError: If not connected to browser.
        """
        return self._browser.send(method, params, self._session_id)

    def execute(self, method: str, params: dict | None = None, timeout: float | None = None) -> Any:
        """Send CDP command synchronously via BrowserSession.

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
            raise TimeoutError(f"Command {method} timed out")

    def _handle_event(self, data: dict) -> None:
        """Handle CDP event routed from BrowserSession.

        Extracted from old _on_message event path:
        - Store in DuckDB with indexed fields
        - Track Fetch.requestPaused count
        - Prune old events periodically
        - Dispatch event callbacks
        - Trigger SSE broadcast for state-affecting events

        Args:
            data: CDP event dictionary with 'method' and 'params'.
        """
        try:
            method = data.get("method", "")
            request_id = self._extract_request_id(data)

            # Store AS-IS in DuckDB with indexed fields for fast lookups
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
            logger.error(f"Error handling event: {e}")

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

    def has_body_capture(self, request_id: str) -> bool | None:
        """Check if response body was already captured successfully.

        Args:
            request_id: Network request ID from CDP events.

        Returns:
            True if body captured successfully, False if capture failed, None if not attempted.
        """
        try:
            rows = self._db_execute(
                """
                SELECT json_extract(event, '$.params.capture.ok') as ok
                FROM events
                WHERE method = 'Network.responseBodyCaptured'
                  AND request_id = ?
                LIMIT 1
                """,
                [request_id],
            )
            if rows:
                ok_value = rows[0][0]
                return ok_value == "true" or ok_value is True
            return None  # No capture attempted
        except Exception:
            return None

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
        """Check if session is still attached and browser WS is alive.

        Returns:
            True if session is attached and browser is connected.
        """
        return self._browser.get_session(self._session_id) is not None and self._browser.is_connected

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
