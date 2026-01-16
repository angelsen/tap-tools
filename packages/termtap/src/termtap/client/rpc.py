"""Lightweight daemon client.

PUBLIC API:
  - DaemonClient: Sync/async client for daemon RPC
  - DaemonNotRunning: Exception when daemon is not available
  - build_client_context: Build client context from environment (re-exported from tmux.ops)
"""

import json
import socket
import time
from typing import Any

from ..paths import SOCKET_PATH
from ..tmux.ops import build_client_context

__all__ = ["DaemonClient", "DaemonNotRunning", "build_client_context"]


class DaemonNotRunning(Exception):
    """Raised when daemon is not running."""

    pass


class DaemonClient:
    """Thin client for termtap daemon."""

    def __init__(self, auto_start: bool = False):
        """Initialize client.

        Args:
            auto_start: Deprecated, always False. Daemon must be started via entry points.
        """
        self._request_id = 0

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float | None = 30.0) -> Any:
        """Make synchronous RPC call.

        Args:
            method: RPC method name
            params: Optional parameters
            timeout: Socket timeout in seconds

        Returns:
            Result from RPC call

        Raises:
            DaemonNotRunning: If daemon is not running
            RPCError: If RPC returns an error
        """

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._request_id,
        }

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            sock.connect(str(SOCKET_PATH))
            sock.sendall(json.dumps(request).encode() + b"\n")

            # Read response
            response_data = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in response_data:
                    break

            response = json.loads(response_data.decode())

            if "error" in response:
                error = response["error"]
                raise RPCError(error["code"], error["message"], error.get("data"))

            return response.get("result")

        except socket.error as e:
            raise DaemonNotRunning(f"Socket error: {e}")
        finally:
            sock.close()

    def execute(self, pane_id: str, command: str) -> dict:
        """Execute command in pane.

        Polls until resolved. Caller handles interruption (Ctrl+C).

        Args:
            pane_id: Pane ID (%format)
            command: Command to execute

        Returns:
            Result dict with status and output
        """
        client_context = build_client_context()
        params = {"target": pane_id, "command": command, "client_context": client_context}
        result = self.call("execute", params)
        status = result.get("status")
        if status in ("error", "busy"):
            return result
        if status in ("ready_check", "watching"):
            return self._poll_until_resolved(result["action_id"])
        return result

    def send(self, pane_id: str, message: str) -> dict:
        """Send message to pane (alias for execute)."""
        client_context = build_client_context()
        return self.call("send", {"target": pane_id, "message": message, "client_context": client_context})

    def interrupt(self, pane_id: str) -> dict:
        """Send Ctrl+C to pane."""
        return self.call("interrupt", {"target": pane_id})

    def ls(self) -> dict:
        """List panes."""
        return self.call("ls")

    def ping(self) -> dict:
        """Check if daemon is responsive."""
        return self.call("ping")

    def debug_eval(self, code: str) -> dict:
        """Execute Python code in daemon with state context.

        Args:
            code: Python expression to evaluate

        Returns:
            dict with result, logs (if any), error (if any)
        """
        return self.call("debug_eval", {"code": code})

    def select_pane(self, command: str) -> dict:
        """Request pane selection via interaction queue.

        Polls until resolved. Caller handles interruption (Ctrl+C).

        Args:
            command: Command name that needs a target pane

        Returns:
            dict with status ("completed", "cancelled", "error")
            and optionally "pane" or "error" fields
        """
        client_context = build_client_context()
        result = self.call("select_pane", {"command": command, "client_context": client_context})
        if result.get("status") != "selecting_pane":
            return result
        status = self._poll_until_resolved(result["action_id"])
        # Extract pane from result
        if status.get("status") == "completed" and status.get("result"):
            return {"status": "completed", "pane": status["result"].get("pane")}
        return status

    def select_panes(self, command: str) -> dict:
        """Request multi-pane selection via interaction queue.

        Polls until resolved. Caller handles interruption (Ctrl+C).

        Args:
            command: Command name that needs target panes

        Returns:
            dict with status ("completed", "cancelled", "error")
            and optionally "panes" (list) or "error" fields
        """
        client_context = build_client_context()
        result = self.call("select_panes", {"command": command, "client_context": client_context})
        if result.get("status") != "selecting_pane":
            return result
        status = self._poll_until_resolved(result["action_id"])
        # Extract panes from result
        if status.get("status") == "completed" and status.get("result"):
            return {"status": "completed", "panes": status["result"].get("panes", [])}
        return status

    def _poll_until_resolved(self, action_id: str) -> dict:
        """Poll action status until resolved.

        Polls forever. Caller handles interruption (Ctrl+C).

        Args:
            action_id: Action ID to poll

        Returns:
            Final status dict
        """
        # States that mean "still in progress"
        in_progress_states = ("selecting_pane", "ready_check", "watching", "not_found")
        while True:
            status = self.call("get_status", {"action_id": action_id})
            if status.get("status") not in in_progress_states:
                return status
            time.sleep(0.5)


class RPCError(Exception):
    """RPC error from daemon."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")
