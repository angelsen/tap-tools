"""Action management RPC handlers.

Handlers for resolve, get_queue, get_status, select_pane, select_panes.
"""

from typing import Any

from ...pane import Pane
from ..context import DaemonContext

__all__ = ["register_handlers"]


def register_handlers(rpc, ctx: DaemonContext):
    """Register action management handlers.

    Args:
        rpc: RPCDispatcher instance
        ctx: DaemonContext with daemon dependencies
    """

    @rpc.method("resolve")
    async def _resolve(action_id: str, result: dict[str, Any]):
        """Resolve action with user response.

        Handles state transitions:
        - READY_CHECK + ready: mark stream, send command, transition to WATCHING
        - WATCHING + ready: capture output since mark, complete action
        - Otherwise: just resolve as-is
        """
        from ...tmux.ops import send_keys
        from ..queue import ActionState

        action = ctx.queue.get(action_id)
        if not action:
            return {"ok": False, "error": "Action not found"}

        # Handle READY_CHECK → WATCHING transition
        if action.state == ActionState.READY_CHECK and result.get("state") == "ready":
            pane = ctx.pane_manager.get_or_create(action.pane_id)
            action.pair_mode = result.get("pair_mode", False)
            action.matched_ready_pattern = result.get("pattern")  # Capture for pairing later
            pane.screen.clear()
            send_keys(action.pane_id, action.command)

            action.state = ActionState.WATCHING
            pane.action = action
            pane.bytes_since_watching = 0  # Reset counter for new data tracking

            await ctx.daemon.broadcast_event({"type": "action_watching", "id": action_id, "action": action.to_dict()})
            return {"ok": True, "status": "watching"}

        # Handle READY_CHECK + busy (terminal is busy, capture current output)
        if action.state == ActionState.READY_CHECK and result.get("state") == "busy":
            pane = ctx.pane_manager.get_or_create(action.pane_id)
            output = Pane.get(action.pane_id, pane).content

            action.result = {"output": output, "truncated": False, "state": "busy"}
            ctx.queue.resolve(action_id, action.result)

            await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
            return {"ok": True, "status": "busy", "result": action.result}

        # Handle WATCHING + busy (terminal became busy, capture current output)
        if action.state == ActionState.WATCHING and result.get("state") == "busy":
            pane = ctx.pane_manager.get_or_create(action.pane_id)
            output = Pane.get(action.pane_id, pane).content

            action.result = {"output": output, "truncated": False, "state": "busy"}
            ctx.queue.resolve(action_id, action.result)
            pane.action = None

            await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
            return {"ok": True, "status": "busy", "result": action.result}

        # Handle WATCHING completion
        if action.state == ActionState.WATCHING and result.get("state") == "ready":
            pane = ctx.pane_manager.get_or_create(action.pane_id)
            output = Pane.get(action.pane_id, pane).content

            action.result = {"output": output, "truncated": False, "state": "ready"}
            ctx.queue.resolve(action_id, action.result)

            await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
            return {"ok": True, "status": "completed", "result": action.result}

        # Handle SELECTING_PANE resolution (pane selected by user)
        if action.state == ActionState.SELECTING_PANE:
            selected_pane = result.get("pane_id") or result.get("panes")
            if selected_pane:
                ctx.queue.resolve(action_id, result)
                await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
                return {"ok": True, "status": "completed", "result": result}

        ctx.queue.resolve(action_id, result)
        await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
        return {"ok": True}

    @rpc.method("cancel")
    async def _cancel(action_id: str):
        """Cancel an action."""
        action = ctx.queue.get(action_id)
        if not action:
            return {"ok": False, "error": "Action not found"}

        ctx.queue.cancel(action_id, "User cancelled")
        await ctx.daemon.broadcast_event({"type": "action_cancelled", "id": action_id})
        return {"ok": True}

    @rpc.method("get_queue")
    async def _get_queue():
        return {"actions": ctx.queue.to_dict()}

    @rpc.method("get_status")
    async def _get_status(action_id: str):
        from ..queue import ActionState

        action = ctx.queue.get(action_id)
        if not action:
            return {"status": "not_found"}
        if action.state == ActionState.COMPLETED:
            return {"status": "completed", "result": action.result}
        if action.state == ActionState.CANCELLED:
            return {"status": "cancelled", "result": action.result}
        if action.state == ActionState.WATCHING:
            return {"status": "watching"}
        if action.state == ActionState.READY_CHECK:
            return {"status": "ready_check"}
        if action.state == ActionState.SELECTING_PANE:
            return {"status": "selecting_pane"}
        return {"status": "unknown"}

    @rpc.method("select_pane")
    async def _select_pane(command: str, client_context: dict):
        from ...tmux.ops import list_panes
        from ..queue import ActionState

        panes = list_panes()

        if not panes:
            return {"status": "error", "error": "No panes available"}

        if len(panes) == 1:
            return {"status": "completed", "pane": panes[0].pane_id}

        action = ctx.queue.add(
            pane_id="",
            command=command,
            state=ActionState.SELECTING_PANE,
            client_context=client_context,
        )

        await ctx.daemon.broadcast_event({"type": "action_added", "action": action.to_dict()})
        return {"status": "selecting_pane", "action_id": action.id}

    @rpc.method("select_panes")
    async def _select_panes(command: str, client_context: dict):
        """Select multiple panes via companion UI."""
        from ...tmux.ops import list_panes
        from ..queue import ActionState

        panes = list_panes()
        if not panes:
            return {"status": "error", "error": "No panes available"}

        action = ctx.queue.add(
            pane_id="",
            command=command,
            state=ActionState.SELECTING_PANE,
            multi_select=True,
            client_context=client_context,
        )

        await ctx.daemon.broadcast_event({"type": "action_added", "action": action.to_dict()})
        return {"status": "selecting_pane", "action_id": action.id}
