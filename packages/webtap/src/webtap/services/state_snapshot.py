"""Immutable state snapshots for thread-safe SSE broadcasting.

PUBLIC API:
  - StateSnapshot: Frozen dataclass for thread-safe state access
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of WebTap state for thread-safe SSE broadcasting.

    Frozen dataclass provides inherent thread safety - multiple threads can
    read simultaneously without locks. Updated atomically when state changes.

    Attributes:
        connected: Whether connected to Chrome page (any target).
        event_count: Total CDP events stored.
        fetch_enabled: Whether fetch interception is active.
        fetch_rules: Dict with capture/block/mock rules if enabled.
        capture_count: Number of bodies captured this session.
        enabled_filters: Tuple of enabled filter category names.
        disabled_filters: Tuple of disabled filter category names.
        tracked_targets: Tuple of target IDs for default aggregation scope.
        connections: Tuple of connection info dicts (each has target, title, url, state).
        inspect_active: Whether element inspection mode is active.
        inspecting_target: Which target is being inspected.
        selections: Dict of selected elements (id -> element data).
        prompt: Browser prompt text (reserved for future use).
        pending_count: Number of pending element selections being processed.
        errors: Dict of errors by target ID.
        notices: List of active notices for multi-surface display.
    """

    # Connection state
    connected: bool

    # Event state
    event_count: int

    # Fetch interception state
    fetch_enabled: bool
    fetch_rules: dict | None
    capture_count: int

    # Filter state
    enabled_filters: tuple[str, ...]
    disabled_filters: tuple[str, ...]

    # Multi-target state
    tracked_targets: tuple[str, ...]
    connections: tuple[dict, ...]

    # Browser/DOM state
    inspect_active: bool
    inspecting_target: str | None
    selections: dict[str, Any]
    prompt: str
    pending_count: int

    # Error state
    errors: dict[str, dict[str, Any]]

    # Notice state
    notices: list[dict[str, Any]]

    @classmethod
    def create_empty(cls) -> "StateSnapshot":
        """Create empty snapshot for disconnected state."""
        return cls(
            connected=False,
            event_count=0,
            fetch_enabled=False,
            fetch_rules=None,
            capture_count=0,
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
