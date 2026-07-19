"""Shared helper functions for RPC handlers.

PUBLIC API:
  - format_queue_state: Format queue for debug output
  - format_panes_state: Format pane manager for debug output
  - format_patterns_state: Format patterns for debug output
  - make_serializable: Convert objects to JSON-serializable format
  - resolve_pane_target: Validate a pane target, returning (pane_id, None) or (None, error_response)
  - complete_action: Single completion path for queue actions
  - begin_watching: Single WATCHING-transition path for queue actions
"""

from typing import Any

from ...pane import Pane
from ...tmux.ops import paste_text
from ..queue import Action, ActionState

__all__ = [
    "format_queue_state",
    "format_panes_state",
    "format_patterns_state",
    "make_serializable",
    "resolve_pane_target",
    "complete_action",
    "begin_watching",
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


def resolve_pane_target(target: str) -> tuple[str, None] | tuple[None, dict]:
    """Validate a pane target.

    Args:
        target: Pane target string to validate

    Returns:
        (pane_id, None) if valid, or (None, error_response) if invalid.
    """
    from ...tmux.resolution import validate_pane_id

    pane_id = validate_pane_id(target)
    if not pane_id:
        return None, {"status": "error", "error": f"Invalid pane ID format: {target}. Use %id format (e.g., %42)."}
    return pane_id, None


def begin_watching(pane_manager: Any, action: Action) -> None:
    """Transition an action to WATCHING: mark stream, paste command, attach to pane.

    Single transition path for all WATCHING starts (execute pre-check,
    manual resolve, auto-resolve). bytes_since_watching must reset here:
    PaneManager.feed only auto-resolves after fresh output arrives, and a
    stale counter from a previous action on the same pane voids that guard.
    """
    pane = pane_manager.get_or_create(action.pane_id)
    pane.mark_output_start()
    paste_text(action.pane_id, action.command)
    action.state = ActionState.WATCHING
    pane.action = action
    pane.bytes_since_watching = 0


async def complete_action(ctx: Any, action: Action, *, state: str | None = None, result: dict | None = None) -> dict:
    """Complete a queue action: set result, resolve queue, clear pane binding, broadcast.

    Single completion path for all handler-side action completions. Always
    clears pane.action and busy tracking regardless of prior state -- a
    completed action must not remain attached to the pane.

    Args:
        ctx: DaemonContext with daemon dependencies
        action: Action being completed
        state: If given, captures live pane output with this state label
        result: If state is not given, used as the action result directly

    Returns:
        {"status": "completed" | "busy", "result": action.result}
    """
    if state is not None:
        pane = ctx.pane_manager.get_or_create(action.pane_id)
        action.result = {"output": Pane.get(action.pane_id, pane).content, "truncated": False, "state": state}
    else:
        action.result = result or {}

    ctx.queue.resolve(action.id, action.result)

    pane = ctx.pane_manager.panes.get(action.pane_id)
    if pane is not None and pane.action is action:
        pane.action = None
    ctx.pane_manager._busy_seen.discard(action.id)

    await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action.id})
    return {"status": "busy" if state == "busy" else "completed", "result": action.result}
