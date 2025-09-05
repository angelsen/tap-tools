"""CDP Session with native event storage.

PUBLIC API:
  - CDPSession: WebSocket-based CDP client with DuckDB event storage
"""

import json
import logging
import threading
from concurrent.futures import Future, TimeoutError
from typing import Any

import duckdb
import requests
import websocket

logger = logging.getLogger(__name__)


class CDPSession:
    """WebSocket-based CDP client with native event storage.

    Stores CDP events as-is in DuckDB for minimal overhead and maximum flexibility.
    Provides field discovery and query capabilities for dynamic data exploration.

    Attributes:
        port: Chrome debugging port.
        timeout: Default timeout for execute() calls.
        db: DuckDB connection for event storage.
        field_paths: Live field lookup for query building.
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

        # CDP request/response tracking
        self._next_id = 1
        self._pending: dict[int, Future] = {}
        self._lock = threading.Lock()

        # DuckDB storage - store events AS-IS
        self.db = duckdb.connect(":memory:")

        self.db.execute("CREATE TABLE events (event JSON)")

        # Live field path lookup for fast discovery
        # Maps lowercase field names to their full paths with original case
        self.field_paths: dict[str, set[str]] = {}

    def list_pages(self) -> list[dict]:
        """List available Chrome pages via HTTP API.

        Returns:
            List of page dictionaries with webSocketDebuggerUrl.
        """
        try:
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=2)
            resp.raise_for_status()
            pages = resp.json()
            return [p for p in pages if p.get("type") == "page" and "webSocketDebuggerUrl" in p]
        except Exception as e:
            logger.error(f"Failed to list pages: {e}")
            return []

    def connect(self, page_index: int | None = None, page_id: str | None = None) -> None:
        """Connect to Chrome page via WebSocket.

        Establishes WebSocket connection and starts event collection.
        Does not auto-enable CDP domains - use execute() for that.

        Args:
            page_index: Index of page to connect to. Defaults to 0.
            page_id: Stable page ID across tab reordering.

        Raises:
            RuntimeError: If already connected or no pages available.
            ValueError: If page_id not found.
            IndexError: If page_index out of range.
            TimeoutError: If connection fails within 5 seconds.
        """
        if self.ws_app:
            raise RuntimeError("Already connected")

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
                "ping_interval": 30,  # Ping every 30s
                "ping_timeout": 10,  # Wait 10s for pong
                "reconnect": 5,  # Auto-reconnect with max 5s delay
                "skip_utf8_validation": True,  # Faster
            },
        )
        self.ws_thread.daemon = True
        self.ws_thread.start()

        # Wait for connection
        if not self.connected.wait(timeout=5):
            self.disconnect()
            raise TimeoutError("Failed to connect to Chrome")

    def disconnect(self) -> None:
        """Disconnect WebSocket and clean up resources."""
        if self.ws_app:
            self.ws_app.close()
            self.ws_app = None

        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=2)
            self.ws_thread = None

        self.connected.clear()
        self.page_info = None

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

            # CDP event - store AS-IS in DuckDB and update field lookup
            elif "method" in data:
                self.db.execute("INSERT INTO events VALUES (?)", [json.dumps(data)])
                self._update_field_lookup(data)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, code, reason):
        """Handle WebSocket closure and cleanup."""
        logger.info(f"WebSocket closed: {code} {reason}")
        self.connected.clear()

        # Fail pending commands
        with self._lock:
            for future in self._pending.values():
                future.set_exception(RuntimeError("Connection closed"))
            self._pending.clear()

    def _extract_paths(self, obj, parent_key=""):
        """Extract all JSON paths from nested dict structure.

        Args:
            obj: Dictionary to extract paths from.
            parent_key: Current path prefix.
        """
        paths = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                paths.append(new_key)
                if isinstance(v, dict):
                    paths.extend(self._extract_paths(v, new_key))
        return paths

    def _update_field_lookup(self, data):
        """Update field_paths lookup with new event data.

        Args:
            data: CDP event dictionary.
        """
        event_type = data.get("method", "unknown")
        paths = self._extract_paths(data)

        for path in paths:
            # Store with event type prefix using colon separator
            full_path = f"{event_type}:{path}"

            # Index by each part of the path for flexible searching
            parts = path.split(".")
            for part in parts:
                key = part.lower()
                if key not in self.field_paths:
                    self.field_paths[key] = set()
                self.field_paths[key].add(full_path)  # Store with event type and original case

    def discover_field_paths(self, search_key: str) -> list[str]:
        """Discover all JSON paths containing the search key.

        Used by build_query for dynamic field discovery.

        Args:
            search_key: Field name to search for like "url" or "status".

        Returns:
            Sorted list of full paths with event type prefixes.
        """
        search_key = search_key.lower()
        paths = set()

        # Find all field names that contain our search key
        for field_name, field_paths in self.field_paths.items():
            if search_key in field_name:
                paths.update(field_paths)

        return sorted(list(paths))  # Sort for consistent results

    def clear_events(self) -> None:
        """Clear all stored events and reset field lookup."""
        self.db.execute("DELETE FROM events")
        self.field_paths.clear()

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
        result = self.db.execute(sql, params or [])
        return result.fetchall() if result else []

    def fetch_body(self, request_id: str) -> dict | None:
        """Fetch response body via Network.getResponseBody CDP call.

        Args:
            request_id: Network request ID from CDP events.

        Returns:
            Dict with 'body' and 'base64Encoded' keys, or None if failed.
        """
        try:
            return self.execute("Network.getResponseBody", {"requestId": request_id})
        except Exception as e:
            logger.debug(f"Failed to fetch body for {request_id}: {e}")
            return None

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket connection is active.

        Returns:
            True if connected to Chrome page.
        """
        return self.connected.is_set()
