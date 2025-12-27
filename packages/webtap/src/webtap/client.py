"""JSON-RPC 2.0 client for WebTap daemon communication.

PUBLIC API:
  - RPCClient: JSON-RPC 2.0 client for daemon communication
  - RPCError: Exception raised for RPC errors
"""

import logging
import os
import subprocess
import uuid
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class RPCError(Exception):
    """RPC error with code, message, and optional data."""

    def __init__(self, code: str, message: str, data: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class RPCClient:
    """Simple JSON-RPC 2.0 client for WebTap daemon.

    All daemon communication goes through `call()`:

        client.call("connect", page=0)
        client.call("network", limit=50, type="xhr")
        client.call("status")

    The client tracks epoch for stale request detection.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0, client_type: str = "repl"):
        from webtap.daemon import get_daemon_url

        self.base_url = base_url or get_daemon_url()
        self.epoch = 0
        self._client_type = client_type
        self._client = httpx.Client(timeout=timeout)

    def _get_client_headers(self) -> dict[str, str]:
        """Build client tracking headers for RPC requests.

        Returns:
            Dict of headers with version, type, and context information
        """
        from webtap import __version__

        headers = {
            "X-Webtap-Version": __version__,
            "X-Webtap-Client-Type": self._client_type,
        }

        # Build context string
        context_parts = []

        # Detect tmux
        if os.environ.get("TMUX"):
            tmux_pane = os.environ.get("TMUX_PANE", "")
            # Get session:window from tmux
            try:
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#{session_name}:#{window_index}"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0:
                    context_parts.append(f"tmux:{result.stdout.strip()}{tmux_pane}")
            except Exception:
                context_parts.append("tmux:unknown")

        # Add cwd
        context_parts.append(os.getcwd())

        headers["X-Webtap-Context"] = ":".join(context_parts)
        return headers

    def call(self, method: str, **params) -> dict[str, Any]:
        """Call RPC method. Raises RPCError on error."""
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": str(uuid.uuid4()),
        }

        # Only send epoch if we've synced with server (non-zero)
        # Server validates epoch only if provided, so first call syncs without validation
        if self.epoch > 0:
            request["epoch"] = self.epoch

        try:
            response = self._client.post(f"{self.base_url}/rpc", json=request, headers=self._get_client_headers())
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to daemon at {self.base_url}: {e}")
            raise RuntimeError("Cannot connect to daemon. Is it running? Try 'webtap --daemon' to start it.") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error from daemon: {e}")
            raise

        # Update epoch from server response (always sync)
        if "epoch" in data:
            self.epoch = data["epoch"]

        # Check for RPC error
        if "error" in data:
            err = data["error"]
            raise RPCError(err.get("code", "UNKNOWN"), err.get("message", "Unknown error"), err.get("data"))

        return data.get("result", {})

    def close(self):
        """Close the HTTP client."""
        self._client.close()


__all__ = ["RPCClient", "RPCError"]
