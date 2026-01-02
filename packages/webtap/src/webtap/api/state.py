"""State snapshot building for SSE broadcasting.

PUBLIC API:
  - get_full_state: Get complete WebTap state for SSE broadcasting
"""

import hashlib
from typing import Any, Dict

import webtap.api.app as app_module

__all__ = ["get_full_state"]


def _stable_hash(data: str) -> str:
    """Generate deterministic hash for frontend change detection."""
    return hashlib.md5(data.encode()).hexdigest()[:16]


def get_full_state() -> Dict[str, Any]:
    """Get complete WebTap state for SSE broadcasting.

    Thread-safe, zero-lock reads from immutable snapshot.
    No blocking I/O - returns cached snapshot immediately.

    Returns:
        Dictionary with connection state, events, fetch status, filters,
        browser state (selections, inspect mode), errors, and content hashes
        for efficient frontend change detection.
    """
    if not app_module.app_state:
        return {
            "connectionState": "disconnected",
            "epoch": 0,
            "connected": False,
            "events": {"total": 0},
            "fetch": {"enabled": False, "rules": None, "capture_count": 0},
            "filters": {"enabled": [], "disabled": []},
            "browser": {"inspect_active": False, "selections": {}, "prompt": "", "pending_count": 0},
            "chrome": {"available": False, "port": 9222},
            "error": None,
        }

    snapshot = app_module.app_state.service.get_state_snapshot()

    # Get connection state from snapshot and epoch from ConnectionManager
    connection_state = "connected" if snapshot.connected else "disconnected"
    epoch = app_module.app_state.service.conn_mgr.epoch

    # Get tracked clients from RPC framework
    clients = app_module.app_state.service.rpc.get_tracked_clients() if app_module.app_state.service.rpc else {}

    from webtap import __version__

    daemon_version = __version__

    # Compute content hashes for frontend change detection
    selections_hash = _stable_hash(str(sorted(snapshot.selections.keys())))
    filters_hash = _stable_hash(f"{sorted(snapshot.enabled_filters)}")
    fetch_hash = _stable_hash(f"{snapshot.fetch_enabled}:{snapshot.fetch_rules}:{snapshot.capture_count}")
    errors_hash = _stable_hash(str(sorted(snapshot.errors.items())))
    targets_hash = _stable_hash(f"{sorted(snapshot.tracked_targets)}:{len(snapshot.connections)}")

    # Convert snapshot to frontend format
    return {
        "connectionState": connection_state,
        "epoch": epoch,
        "daemon_version": daemon_version,
        "clients": clients,
        "connected": snapshot.connected,
        "events": {"total": snapshot.event_count},
        "fetch": {
            "enabled": snapshot.fetch_enabled,
            "rules": snapshot.fetch_rules,
            "capture_count": snapshot.capture_count,
        },
        "filters": {"enabled": list(snapshot.enabled_filters), "disabled": list(snapshot.disabled_filters)},
        # Multi-target state (connections now include state field)
        "tracked_targets": list(snapshot.tracked_targets),
        "connections": list(snapshot.connections),
        "browser": {
            "inspect_active": snapshot.inspect_active,
            "inspecting": snapshot.inspecting_target,
            "selections": snapshot.selections,
            "prompt": snapshot.prompt,
            "pending_count": snapshot.pending_count,
        },
        "chrome": app_module.app_state.service.watcher.to_dict(),
        "errors": snapshot.errors,
        "notices": snapshot.notices,
        # Content hashes for efficient change detection
        "selections_hash": selections_hash,
        "filters_hash": filters_hash,
        "fetch_hash": fetch_hash,
        "errors_hash": errors_hash,
        "targets_hash": targets_hash,
    }
