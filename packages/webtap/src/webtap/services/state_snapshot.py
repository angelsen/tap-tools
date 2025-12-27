"""Immutable state snapshots for thread-safe SSE broadcasting.

PUBLIC API:
  - StateSnapshot: Frozen dataclass for thread-safe state access
"""

from dataclasses import dataclass
from typing import Any, List, Dict


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of WebTap state.

    Frozen dataclass provides inherent thread safety - multiple threads can
    read simultaneously without locks. Updated atomically when state changes.

    Used by SSE broadcast to avoid lock contention between asyncio event loop
    and background threads (WebSocket, disconnect handlers).

    Attributes:
        connected: Whether connected to Chrome page (any target)
        page_id: Stable page identifier (empty if not connected)
        page_title: Page title (empty if not connected)
        page_url: Page URL (empty if not connected)
        event_count: Total CDP events stored
        fetch_enabled: Whether fetch interception is active
        paused_count: Number of paused requests (if fetch enabled)
        enabled_filters: Tuple of enabled filter category names
        disabled_filters: Tuple of disabled filter category names
        tracked_targets: Tuple of target IDs for default aggregation scope (empty = all)
        connections: Tuple of connection info dicts (target, title, url)
        inspect_active: Whether element inspection mode is active
        selections: Dict of selected elements (id -> element data)
        prompt: Browser prompt text (unused, reserved)
        pending_count: Number of pending element selections being processed
        errors: Dict of errors by target ID (target_id -> {message, timestamp})
        notices: List of active notices for multi-surface display
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
    response_stage: bool
    paused_count: int

    # Filter state (immutable tuples)
    enabled_filters: tuple[str, ...]
    disabled_filters: tuple[str, ...]

    # Multi-target state
    tracked_targets: tuple[str, ...]  # Default scope for aggregation (empty = all)
    connections: tuple[dict, ...]  # Connection info: [{target, title, url}, ...]

    # Browser/DOM state
    inspect_active: bool
    inspecting_target: str | None  # Which target is being inspected
    selections: dict[str, Any]  # Dict is mutable but replaced atomically
    prompt: str
    pending_count: int

    # Error state - per-target errors
    errors: dict[str, dict[str, Any]]  # {target_id: {message: str, timestamp: float}}

    # Notice state
    notices: List[Dict[str, Any]]

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
            response_stage=False,
            paused_count=0,
            enabled_filters=(),
            disabled_filters=(),
            tracked_targets=(),
            connections=(),
            inspect_active=False,
            inspecting_target=None,
            selections={},
            prompt="",
            pending_count=0,
            errors={},
            notices=[],
        )


__all__ = ["StateSnapshot"]
