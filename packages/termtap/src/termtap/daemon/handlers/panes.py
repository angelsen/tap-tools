"""Pane management RPC handlers.

Handlers for touch, get_pane_data, ls, cleanup.
"""

from ..context import DaemonContext

__all__ = ["register_handlers"]


def register_handlers(rpc, ctx: DaemonContext):
    """Register pane management handlers.

    Args:
        rpc: RPCDispatcher instance
        ctx: DaemonContext with daemon dependencies
    """

    @rpc.method("touch")
    async def _touch(pane_id: str):
        """Register intentional pane access without streaming.

        Used by direct pane reads (e.g., pane() command) to update
        last_accessed for working-set tracking.
        """
        ctx.pane_manager.get_or_create(pane_id)
        return {"touched": pane_id}

    @rpc.method("get_pane_data")
    async def _get_pane_data(pane_id: str, lines: int = 20):
        """Get live pane data for display."""
        from ...pane import Pane
        from ...tmux.ops import get_pane

        # Touch first to register intentional access (e.g., pattern screen viewing)
        ctx.pane_manager.get_or_create(pane_id)

        captured = Pane.capture_tail(pane_id, lines)
        # Get swp from pane info (Pane doesn't include this)
        info = get_pane(pane_id)

        return {
            "content": captured.content,
            "process": captured.process,  # Use Pane's synced process
            "swp": info.swp if info else "",
        }

    @rpc.method("ls")
    async def _ls():
        from dataclasses import asdict

        from ...tmux.ops import list_panes

        panes = list_panes()
        result = []
        for p in panes:
            pane_dict = asdict(p)
            # Add last_accessed from tracked panes (0.0 if not tracked)
            tracked = ctx.pane_manager.panes.get(p.pane_id)
            pane_dict["last_accessed"] = tracked.last_accessed if tracked else 0.0
            result.append(pane_dict)

        return {"panes": result}

    @rpc.method("cleanup")
    async def _cleanup():
        removed = ctx.pane_manager.cleanup_dead()
        return {"removed": len(removed)}
