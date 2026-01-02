"""JSON-RPC 2.0 client for WebTap daemon communication.

PUBLIC API:
  - RPCClient: JSON-RPC 2.0 client for daemon communication
  - RPCError: Re-exported from rpc.errors for convenience
"""

import logging
import os
import subprocess
import time
import uuid
from typing import Any

import httpx

from webtap.rpc.errors import RPCError

logger = logging.getLogger(__name__)


class RPCClient:
    """Simple JSON-RPC 2.0 client for WebTap daemon.

    All daemon communication goes through `call()`:

        client.call("connect", page=0)
        client.call("network", limit=50, type="xhr")
        client.call("status")

    The client tracks epoch for stale request detection.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        client_type: str = "repl",
        max_retries: int = 3,
    ):
        from webtap.daemon import get_daemon_url

        self.base_url = base_url or get_daemon_url()
        self.epoch = 0
        self._client_type = client_type
        self._max_retries = max_retries
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
        """Call RPC method with auto-start and retry on transient errors.

        Auto-starts daemon if not running, then retries connection errors
        with exponential backoff (1s, 2s, 4s).
        """
        from webtap.daemon import ensure_daemon

        # Ensure daemon is running (cheap health check if already up)
        ensure_daemon()

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

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post(f"{self.base_url}/rpc", json=request, headers=self._get_client_headers())
                response.raise_for_status()
                data = response.json()

                # Update epoch from server response (always sync)
                if "epoch" in data:
                    self.epoch = data["epoch"]

                # Check for RPC error
                if "error" in data:
                    err = data["error"]
                    raise RPCError(err.get("code", "UNKNOWN"), err.get("message", "Unknown error"), err.get("data"))

                return data.get("result", {})

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self._max_retries:
                    backoff = 2**attempt  # 1s, 2s, 4s
                    logger.debug(f"Daemon connection failed, retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                break
            except httpx.HTTPError as e:
                # Don't retry HTTP errors (4xx, 5xx)
                logger.error(f"HTTP error from daemon: {e}")
                raise

        # All retries exhausted
        raise RuntimeError(f"Cannot connect to daemon after {self._max_retries + 1} attempts.") from last_error

    def close(self):
        """Close the HTTP client."""
        self._client.close()


__all__ = ["RPCClient", "RPCError"]
