"""RPC handler registration for termtap daemon.

PUBLIC API:
  - register_all_handlers: Register all RPC handlers with dispatcher
"""

__all__ = ["register_all_handlers"]


def register_all_handlers(rpc, ctx):
    """Register all RPC method handlers.

    Args:
        rpc: RPCDispatcher instance
        ctx: DaemonContext with daemon dependencies
    """
    from . import actions, commands, diagnostics, panes, patterns

    commands.register_handlers(rpc, ctx)
    actions.register_handlers(rpc, ctx)
    patterns.register_handlers(rpc, ctx)
    panes.register_handlers(rpc, ctx)
    diagnostics.register_handlers(rpc, ctx)
