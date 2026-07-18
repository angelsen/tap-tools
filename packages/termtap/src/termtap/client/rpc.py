"""Lightweight daemon client.

PUBLIC API:
  - DaemonClient: Sync/async client for daemon RPC
  - DaemonNotRunning: Exception when daemon is not available
  - RPCError: RPC error from daemon
"""

import json
import socket
import time
from typing import Any

from ..paths import SOCKET_PATH
from ..protocol import RPCError, encode, request as build_request
from ..tmux.ops import build_client_context

__all__ = ["DaemonClient", "DaemonNotRunning", "RPCError"]


class DaemonNotRunning(Exception):
    """Raised when daemon is not running."""

    pass


class DaemonClient:
    """Thin client for termtap daemon."""

    def __init__(self):
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
        req = build_request(method, params or {}, self._request_id)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            sock.connect(str(SOCKET_PATH))
            sock.sendall(encode(req))

            # Read response
            response_data = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in response_data:
                    break

            if not response_data:
                raise DaemonNotRunning("Daemon closed connection without responding")

            try:
                response = json.loads(response_data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise DaemonNotRunning("Daemon sent an incomplete response (crashed mid-request?)")

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

    def interrupt(self, pane_id: str) -> dict:
        """Send Ctrl+C to pane."""
        return self.call("interrupt", {"target": pane_id})

    def ls(self) -> dict:
        """List panes."""
        return self.call("ls")

    def debug_eval(self, code: str) -> dict:
        """Execute Python code in daemon with state context.

        Args:
            code: Python expression to evaluate

        Returns:
            dict with result, logs (if any), error (if any)
        """
        return self.call("debug_eval", {"code": code})

    def _select(self, method: str, command: str, key: str) -> dict:
        """Shared select-pane(s) flow: call, poll until resolved, extract result key.

        Args:
            method: RPC method name ("select_pane" or "select_panes")
            command: Command name that needs target pane(s)
            key: Result key to extract ("pane" or "panes")

        Returns:
            dict with status ("completed", "cancelled", "error") and,
            on success, the extracted key.
        """
        client_context = build_client_context()
        result = self.call(method, {"command": command, "client_context": client_context})
        if result.get("status") != "selecting_pane":
            return result
        status = self._poll_until_resolved(result["action_id"])
        if status.get("status") == "completed" and status.get("result"):
            return {"status": "completed", key: status["result"].get(key)}
        return status

    def select_pane(self, command: str) -> dict:
        """Request pane selection via interaction queue.

        Polls until resolved. Caller handles interruption (Ctrl+C).

        Args:
            command: Command name that needs a target pane

        Returns:
            dict with status ("completed", "cancelled", "error")
            and optionally "pane" or "error" fields
        """
        return self._select("select_pane", command, "pane")

    def select_panes(self, command: str) -> dict:
        """Request multi-pane selection via interaction queue.

        Polls until resolved. Caller handles interruption (Ctrl+C).

        Args:
            command: Command name that needs target panes

        Returns:
            dict with status ("completed", "cancelled", "error")
            and optionally "panes" (list) or "error" fields
        """
        result = self._select("select_panes", command, "panes")
        if result.get("status") == "completed":
            result["panes"] = result.get("panes") or []
        return result

    def _poll_until_resolved(self, action_id: str) -> dict:
        """Poll action status until resolved.

        Polls forever. Caller handles interruption (Ctrl+C).

        Args:
            action_id: Action ID to poll

        Returns:
            Final status dict
        """
        # States that mean "still in progress"
        in_progress_states = ("selecting_pane", "ready_check", "watching")
        # "not_found" means the daemon lost the action (restart, eviction).
        # Tolerate a few in case of transient races, then give up — polling
        # forever wedges the synchronous MCP tool call.
        not_found_count = 0
        while True:
            status = self.call("get_status", {"action_id": action_id})
            state = status.get("status")
            if state == "not_found":
                not_found_count += 1
                if not_found_count >= 3:
                    return {"status": "error", "error": f"Action {action_id} no longer exists (daemon restarted?)"}
            elif state not in in_progress_states:
                return status
            time.sleep(0.5)
