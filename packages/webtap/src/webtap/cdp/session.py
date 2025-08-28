"""Minimal CDP Session - just connection and send/execute.

WebSocketApp handles the WebSocket, we handle CDP protocol.
"""

import json
import logging
import threading
from collections import defaultdict, deque
from concurrent.futures import Future, TimeoutError
from typing import Any

import requests
import websocket

logger = logging.getLogger(__name__)


class CDPSession:
    """Minimal CDP client - just connect, send, execute.

    No convenience methods, no auto-enable, just the basics.
    """

    def __init__(self, port: int = 9222, timeout: float = 30):
        """Initialize CDP session.

        Args:
            port: Chrome debugging port
            timeout: Default timeout for execute()
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

        # Store CDP events AS-IS
        self.network_events = defaultdict(list)  # requestId -> [events]
        self.console_events = deque(maxlen=500)  # chronological

    def list_pages(self) -> list[dict]:
        """List available Chrome pages."""
        try:
            resp = requests.get(f"http://localhost:{self.port}/json", timeout=2)
            resp.raise_for_status()
            pages = resp.json()
            return [p for p in pages if p.get("type") == "page" and "webSocketDebuggerUrl" in p]
        except Exception as e:
            logger.error(f"Failed to list pages: {e}")
            return []

    def connect(self, page_index: int = 0) -> None:
        """Connect to Chrome page. Just establishes connection, no auto-enable."""
        if self.ws_app:
            raise RuntimeError("Already connected")

        pages = self.list_pages()
        if not pages:
            raise RuntimeError("No pages available")

        if page_index >= len(pages):
            raise IndexError(f"Page {page_index} out of range")

        page = pages[page_index]
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
        """Disconnect from Chrome."""
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

        Returns a Future. Call future.result(timeout) to get response.

        Args:
            method: CDP method (e.g. "Page.navigate")
            params: Optional parameters

        Returns:
            Future that will contain the 'result' field from CDP response
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

        Blocks until response received or timeout.

        Args:
            method: CDP method (e.g. "Page.navigate")
            params: Optional parameters
            timeout: Override default timeout

        Returns:
            The 'result' field from CDP response
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
        """WebSocket opened."""
        logger.info("WebSocket connected")
        self.connected.set()

    def _on_message(self, ws, message):
        """Handle CDP message - store events AS-IS, resolve futures."""
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

            # CDP event - store AS-IS
            elif "method" in data:
                method = data["method"]

                # Network events - group by requestId
                if method.startswith("Network."):
                    request_id = data.get("params", {}).get("requestId")
                    if request_id:
                        self.network_events[request_id].append(data)

                # Console/Log events - chronological
                elif method in ["Runtime.consoleAPICalled", "Log.entryAdded"]:
                    self.console_events.append(data)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _on_error(self, ws, error):
        """WebSocket error."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, code, reason):
        """WebSocket closed."""
        logger.info(f"WebSocket closed: {code} {reason}")
        self.connected.clear()

        # Fail pending commands
        with self._lock:
            for future in self._pending.values():
                future.set_exception(RuntimeError("Connection closed"))
            self._pending.clear()

    def clear_events(self) -> None:
        """Clear all stored events."""
        self.network_events.clear()
        self.console_events.clear()
