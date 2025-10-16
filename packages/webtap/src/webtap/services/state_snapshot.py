"""Immutable state snapshots for thread-safe SSE broadcasting.

PUBLIC API:
  - StateSnapshot: Frozen dataclass for zero-lock state reads
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of WebTap state.

    Frozen dataclass provides inherent thread safety - multiple threads can
    read simultaneously without locks. Updated atomically when state changes.

    Used by SSE broadcast to avoid lock contention between asyncio event loop
    and background threads (WebSocket, disconnect handlers).

    Attributes:
        connected: Whether connected to Chrome page
        page_id: Stable page identifier (empty if not connected)
        page_title: Page title (empty if not connected)
        page_url: Page URL (empty if not connected)
        event_count: Total CDP events stored
        fetch_enabled: Whether fetch interception is active
        paused_count: Number of paused requests (if fetch enabled)
        enabled_filters: Tuple of enabled filter category names
        disabled_filters: Tuple of disabled filter category names
        inspect_active: Whether element inspection mode is active
        selections: Dict of selected elements (id -> element data)
        prompt: Browser prompt text (unused, reserved)
        pending_count: Number of pending element selections being processed
        error_message: Current error message or None
        error_timestamp: Error timestamp or None
    """

    # Connection state
    connected: bool
    page_id: str
    page_title: str
    page_url: str

    # Event state
    event_count: int

    # Fetch interception state
    fetch_enabled: bool
    paused_count: int

    # Filter state (immutable tuples)
    enabled_filters: tuple[str, ...]
    disabled_filters: tuple[str, ...]

    # Browser/DOM state
    inspect_active: bool
    selections: dict[str, Any]  # Dict is mutable but replaced atomically
    prompt: str
    pending_count: int

    # Error state
    error_message: str | None
    error_timestamp: float | None

    @classmethod
    def create_empty(cls) -> "StateSnapshot":
        """Create empty snapshot for disconnected state."""
        return cls(
            connected=False,
            page_id="",
            page_title="",
            page_url="",
            event_count=0,
            fetch_enabled=False,
            paused_count=0,
            enabled_filters=(),
            disabled_filters=(),
            inspect_active=False,
            selections={},
            prompt="",
            pending_count=0,
            error_message=None,
            error_timestamp=None,
        )


__all__ = ["StateSnapshot"]
