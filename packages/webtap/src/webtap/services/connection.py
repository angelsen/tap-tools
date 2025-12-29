"""Connection lifecycle manager with per-target locking.

PUBLIC API:
  - ConnectionManager: Thread-safe connection lifecycle management
  - ActiveConnection: Tracks an active CDP connection
  - TargetState: Per-target connection state enum
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum

from webtap.cdp import CDPSession


class TargetState(str, Enum):
    """Per-target connection state."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


@dataclass
class ActiveConnection:
    """Tracks an active CDP connection.

    Attributes:
        target: Target ID in format "{port}:{short-id}".
        cdp: CDPSession for browser communication.
        page_info: Page metadata from Chrome.
        connected_at: Unix timestamp when connection was established.
        state: Current connection state.
        inspecting: Whether element inspection mode is active.
    """

    target: str
    cdp: CDPSession
    page_info: dict
    connected_at: float
    state: TargetState = TargetState.CONNECTED
    inspecting: bool = False


__all__ = ["ConnectionManager", "ActiveConnection", "TargetState"]


class ConnectionManager:
    """Thread-safe connection lifecycle management.

    Manages per-target locks for concurrent operations, tracks connection state,
    and provides epoch counter for state change detection.

    Attributes:
        connections: Active connections keyed by target ID
        epoch: Global counter incremented on any state change
    """

    def __init__(self):
        """Initialize ConnectionManager with empty state."""
        self.connections: dict[str, ActiveConnection] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock: threading.Lock = threading.Lock()
        self._epoch: int = 0

    @property
    def epoch(self) -> int:
        """Global epoch counter, incremented on any state change."""
        return self._epoch

    def _get_target_lock(self, target: str) -> threading.Lock:
        """Get or create per-target lock.

        Args:
            target: Target ID

        Returns:
            Lock for the specified target
        """
        with self._global_lock:
            if target not in self._locks:
                self._locks[target] = threading.Lock()
            return self._locks[target]

    def connect(
        self,
        target: str,
        cdp: CDPSession,
        page_info: dict,
    ) -> ActiveConnection:
        """Thread-safe connection registration.

        Idempotent - returns existing connection if already connected.

        Args:
            target: Target ID in format "{port}:{short-id}"
            cdp: CDPSession instance for this connection
            page_info: Page metadata from Chrome

        Returns:
            ActiveConnection for the target
        """
        lock = self._get_target_lock(target)
        with lock:
            if target in self.connections:
                return self.connections[target]

            conn = ActiveConnection(
                target=target,
                cdp=cdp,
                page_info=page_info,
                connected_at=time.time(),
                state=TargetState.CONNECTED,
            )
            with self._global_lock:
                self.connections[target] = conn
                self._epoch += 1
            return conn

    def disconnect(self, target: str) -> bool:
        """Thread-safe disconnection with double-disconnect prevention.

        Args:
            target: Target ID to disconnect

        Returns:
            True if disconnected, False if already disconnecting or not found
        """
        lock = self._get_target_lock(target)
        with lock:
            conn = self.connections.get(target)
            if not conn or conn.state == TargetState.DISCONNECTING:
                return False

            conn.state = TargetState.DISCONNECTING

        # CDP cleanup outside lock (network I/O)
        conn.cdp.disconnect()
        conn.cdp.cleanup()

        with self._global_lock:
            self.connections.pop(target, None)
            self._locks.pop(target, None)
            self._epoch += 1
        return True

    def get(self, target: str) -> ActiveConnection | None:
        """Get connection by target ID.

        Args:
            target: Target ID

        Returns:
            ActiveConnection if exists, None otherwise
        """
        return self.connections.get(target)

    def get_all(self) -> list[ActiveConnection]:
        """Get all active connections.

        Returns:
            List of all ActiveConnection instances
        """
        return list(self.connections.values())

    def set_inspecting(self, target: str, inspecting: bool) -> bool:
        """Set inspection state for a target.

        Args:
            target: Target ID
            inspecting: Whether inspection mode is active

        Returns:
            True if state was set, False if target not found or not connected
        """
        conn = self.connections.get(target)
        if conn and conn.state == TargetState.CONNECTED:
            conn.inspecting = inspecting
            with self._global_lock:
                self._epoch += 1
            return True
        return False

    def remove_from_tracked(self, target: str, tracked_targets: list[str]) -> bool:
        """Remove target from tracked list if present.

        Helper for cleanup operations.

        Args:
            target: Target ID to remove
            tracked_targets: List of tracked targets to modify

        Returns:
            True if removed, False if not found
        """
        if target in tracked_targets:
            tracked_targets.remove(target)
            return True
        return False
