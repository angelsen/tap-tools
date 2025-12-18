"""State management for SSE broadcasting."""

import hashlib
from typing import Any, Dict

import webtap.api.app as app_module


def _stable_hash(data: str) -> str:
    """Generate deterministic hash for frontend change detection.

    Uses MD5 for speed (not security). Returns 16-char hex digest.
    Ensures hashes remain stable across process restarts (unlike Python's hash()).
    """
    return hashlib.md5(data.encode()).hexdigest()[:16]


def get_full_state() -> Dict[str, Any]:
    """Get complete WebTap state for broadcasting.

    Thread-safe, zero-lock reads from immutable snapshot.
    No blocking I/O - returns cached snapshot immediately.

    Returns:
        Dictionary with all state information for SSE clients
    """
    if not app_module.app_state:
        return {
            "connectionState": "disconnected",
            "epoch": 0,
            "connected": False,
            "events": {"total": 0},
            "fetch": {"enabled": False, "paused_count": 0},
            "filters": {"enabled": [], "disabled": []},
            "browser": {"inspect_active": False, "selections": {}, "prompt": "", "pending_count": 0},
            "error": None,
        }

    # Get immutable snapshot (NO LOCKS NEEDED - inherently thread-safe)
    snapshot = app_module.app_state.service.get_state_snapshot()

    # Get connection state and epoch from RPC machine
    machine = app_module.app_state.service.rpc.machine if app_module.app_state.service.rpc else None
    connection_state = machine.state if machine else "disconnected"
    epoch = machine.epoch if machine else 0

    # Compute content hashes for frontend change detection
    # Only computed here when building SSE response (not on every state change)
    selections_hash = _stable_hash(str(sorted(snapshot.selections.keys())))
    filters_hash = _stable_hash(f"{sorted(snapshot.enabled_filters)}")
    fetch_hash = _stable_hash(f"{snapshot.fetch_enabled}:{snapshot.response_stage}:{snapshot.paused_count}")
    page_hash = _stable_hash(f"{snapshot.connected}:{snapshot.page_id}")
    error_hash = _stable_hash(snapshot.error_message) if snapshot.error_message else ""

    # Convert snapshot to frontend format
    return {
        "connectionState": connection_state,
        "epoch": epoch,
        "connected": snapshot.connected,
        "page": {
            "id": snapshot.page_id,
            "title": snapshot.page_title,
            "url": snapshot.page_url,
        }
        if snapshot.connected
        else None,
        "events": {"total": snapshot.event_count},
        "fetch": {
            "enabled": snapshot.fetch_enabled,
            "response_stage": snapshot.response_stage,
            "paused_count": snapshot.paused_count,
        },
        "filters": {"enabled": list(snapshot.enabled_filters), "disabled": list(snapshot.disabled_filters)},
        "browser": {
            "inspect_active": snapshot.inspect_active,
            "selections": snapshot.selections,
            "prompt": snapshot.prompt,
            "pending_count": snapshot.pending_count,
        },
        "error": {"message": snapshot.error_message, "timestamp": snapshot.error_timestamp}
        if snapshot.error_message
        else None,
        # Content hashes for efficient change detection
        "selections_hash": selections_hash,
        "filters_hash": filters_hash,
        "fetch_hash": fetch_hash,
        "page_hash": page_hash,
        "error_hash": error_hash,
    }
