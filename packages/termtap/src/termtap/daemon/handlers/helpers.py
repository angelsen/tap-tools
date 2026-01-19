"""Shared helper functions for RPC handlers.

PUBLIC API:
  - format_queue_state: Format queue for debug output
  - format_panes_state: Format pane manager for debug output
  - format_patterns_state: Format patterns for debug output
  - make_serializable: Convert objects to JSON-serializable format
  - validate_pane_target: Validate pane target string
  - transition_to_watching: Transition action to WATCHING state
  - complete_action: Complete action with result
"""

from ..context import DaemonContext

__all__ = [
    "format_queue_state",
    "format_panes_state",
    "format_patterns_state",
    "make_serializable",
    "validate_pane_target",
    "transition_to_watching",
    "complete_action",
]


def format_queue_state(queue) -> dict:
    """Format queue state for debug output."""
    import time

    now = time.time()

    return {
        "pending": [
            {
                "id": a.id,
                "pane_id": a.pane_id,
                "command": a.command[:50],
                "state": a.state.value,
                "age_seconds": now - a.timestamp,
            }
            for a in queue.pending
        ],
        "resolved_count": len(queue.resolved),
        "utilization": len(queue.pending) / queue.max_size,
    }


def format_panes_state(manager) -> dict:
    """Format pane manager state for debug output."""
    import time

    now = time.time()

    result = {}
    for pane_id, pane in manager.panes.items():
        action_info = None
        if pane.action:
            action_info = {
                "id": pane.action.id,
                "state": pane.action.state.value,
                "age_seconds": now - pane.action.timestamp,
            }

        result[pane_id] = {
            "process": pane.process,
            "collecting": pane_id in manager._active_pipes,
            "bytes_fed": pane.bytes_fed,
            "action": action_info,
            "buffer": {
                "line_count": pane.screen.line_count,
                "base_idx": pane.screen.base_idx,
                "preserve_before": pane.screen.preserve_before,
            },
        }

    return result


def format_patterns_state(patterns) -> dict:
    """Format pattern store state for debug output."""
    process_counts = {}
    for process, states in patterns.patterns.items():
        counts = {state: len(plist) for state, plist in states.items()}
        process_counts[process] = counts

    return {
        "path": str(patterns.path),
        "processes": process_counts,
        "total_patterns": sum(len(plist) for states in patterns.patterns.values() for plist in states.values()),
    }


def make_serializable(obj):
    """Convert non-JSON types to serializable format."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_serializable(v) for v in obj]
    if isinstance(obj, set):
        return list(obj)
    return repr(obj)


def validate_pane_target(target: str) -> str:
    """Validate pane target, raise ValueError if invalid.

    Args:
        target: Pane target string to validate

    Returns:
        Validated pane ID

    Raises:
        ValueError: If pane ID format is invalid
    """
    from ...tmux.ops import validate_pane_id

    pane_id = validate_pane_id(target)
    if not pane_id:
        raise ValueError(f"Invalid pane ID format: {target}. Use %id format (e.g., %42).")
    return pane_id


async def transition_to_watching(ctx: DaemonContext, pane, action_id: str):
    """Transition action from READY_CHECK to WATCHING and broadcast event.

    Args:
        ctx: Daemon context
        pane: Pane terminal object
        action_id: Action ID to transition
    """
    from ..queue import ActionState

    action = ctx.queue.get(action_id)
    if not action:
        return

    action.state = ActionState.WATCHING
    pane.action = action
    pane.bytes_since_watching = 0

    await ctx.daemon.broadcast_event({"type": "action_watching", "id": action_id, "action": action.to_dict()})


async def complete_action(ctx: DaemonContext, action_id: str, result: dict):
    """Complete action with result and broadcast event.

    Args:
        ctx: Daemon context
        action_id: Action ID to complete
        result: Result data to store
    """
    ctx.queue.resolve(action_id, result)
    await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
