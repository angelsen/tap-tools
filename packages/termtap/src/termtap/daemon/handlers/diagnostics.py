"""Diagnostic RPC handlers.

Handlers for interrupt, ping, debug_eval.
"""

from ..context import DaemonContext
from .helpers import format_queue_state, format_panes_state, format_patterns_state, make_serializable

__all__ = ["register_handlers"]


def register_handlers(rpc, ctx: DaemonContext):
    """Register diagnostic handlers.

    Args:
        rpc: RPCDispatcher instance
        ctx: DaemonContext with daemon dependencies
    """

    @rpc.method("interrupt")
    async def _interrupt(target: str):
        from ...tmux.ops import send_keys
        from .helpers import validate_pane_target

        try:
            pane_id = validate_pane_target(target)
        except ValueError as e:
            return {"status": "error", "error": str(e)}

        send_keys(pane_id, "C-c")
        return {"status": "sent"}

    @rpc.method("ping")
    async def _ping():
        return {"pong": True}

    @rpc.method("debug_eval")
    async def _debug_eval(code: str):
        """Execute Python code with daemon state context.

        Args:
            code: Python expression/statement to execute

        Returns:
            dict with result, logs (if any), error (if any)
        """
        from types import SimpleNamespace

        captured = []

        debug_ctx = SimpleNamespace(
            queue=lambda: format_queue_state(ctx.queue),
            panes=lambda: format_panes_state(ctx.pane_manager),
            patterns=lambda: format_patterns_state(ctx.patterns),
            health=lambda: {
                "running": ctx.daemon._running,
                "event_clients": len(ctx.daemon.event_clients),
                "servers": len(ctx.daemon._servers),
                "logs_buffered": len(ctx.daemon._log_buffer),
            },
            logs=lambda n=50: ctx.daemon._log_buffer[-n:] if ctx.daemon._log_buffer else [],
            raw=SimpleNamespace(
                queue=ctx.queue,
                pane_manager=ctx.pane_manager,
                patterns=ctx.patterns,
                daemon=ctx.daemon,
            ),
            log=lambda *args: captured.append(" ".join(str(a) for a in args)),
        )

        try:
            # Use exec() for statements, capture result variable if set
            import builtins

            namespace = {"ctx": debug_ctx, "result": None, "__builtins__": builtins}
            exec(code, namespace)
            result = namespace.get("result")

            # Serialize non-JSON types
            result = make_serializable(result)

            return {
                "result": result,
                **({"logs": captured} if captured else {}),
            }
        except Exception as e:
            return {
                "result": None,
                "error": str(e),
                **({"logs": captured} if captured else {}),
            }
