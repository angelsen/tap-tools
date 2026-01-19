"""Pattern management RPC handlers.

Handlers for learn_pattern, set_linked_busy, get_patterns, remove_pattern,
remove_pair, get_hooks, update_process_config.
"""

import logging

from ...pane import Pane
from ..context import DaemonContext

logger = logging.getLogger(__name__)

__all__ = ["register_handlers"]


def register_handlers(rpc, ctx: DaemonContext):
    """Register pattern management handlers.

    Args:
        rpc: RPCDispatcher instance
        ctx: DaemonContext with daemon dependencies
    """

    @rpc.method("learn_pattern")
    async def _learn_pattern(process: str, pattern: str, state: str):
        ctx.patterns.add(process, pattern, state)
        return {"ok": True}

    @rpc.method("set_linked_busy")
    async def _set_linked_busy(action_id: str, pattern: str):
        """Set linked busy pattern and immediately complete action."""
        from ..queue import ActionState

        action = ctx.queue.get(action_id)
        if action and action.pair_mode:
            pane = ctx.pane_manager.get_or_create(action.pane_id)

            # Store as pair with the matched ready pattern
            if action.matched_ready_pattern:
                ctx.patterns.add_pair(pane.process, action.matched_ready_pattern, pattern)
                logger.info(f"Action {action_id}: learned pair ready={action.matched_ready_pattern} busy={pattern}")
            else:
                # Fallback: just add as standalone busy pattern
                ctx.patterns.add(pane.process, pattern, "busy")

            # IMMEDIATELY COMPLETE (key change!)
            output = Pane.get(action.pane_id, pane).content
            action.result = {"output": output, "truncated": False}
            action.state = ActionState.COMPLETED
            action.linked_busy_pattern = pattern
            ctx.queue.resolve(action_id, action.result)
            pane.action = None

            logger.info(f"Action {action_id}: completed immediately after busy pattern marked")

            await ctx.daemon.broadcast_event({"type": "action_resolved", "id": action_id})
            return {"ok": True, "status": "completed"}

        return {"ok": False, "error": "Not in pair mode"}

    @rpc.method("get_patterns")
    async def _get_patterns(process: str | None = None):
        if process:
            return {"patterns": ctx.patterns.get(process)}
        return {"patterns": ctx.patterns.all()}

    @rpc.method("remove_pattern")
    async def _remove_pattern(process: str, pattern: str, state: str):
        ctx.patterns.remove(process, pattern, state)
        return {"ok": True}

    @rpc.method("remove_pair")
    async def _remove_pair(process: str, ready: str, busy: str):
        ctx.patterns.remove_pair(process, ready, busy)
        return {"ok": True}

    @rpc.method("get_hooks")
    async def _get_hooks(process: str | None = None):
        return {"hooks": ctx.patterns.get_hooks(process)}

    @rpc.method("update_process_config")
    async def _update_process_config(process: str, config: dict):
        ctx.patterns.update_process_config(process, config)
        return {"ok": True}
