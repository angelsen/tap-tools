"""Debug command for daemon state inspection.

PUBLIC API:
  - debug: Execute arbitrary Python code in daemon
"""

from typing import Any

from ..app import app


@app.command(fastmcp={"type": "tool"})
def debug(state, code: str) -> dict[str, Any]:
    """Debug daemon state by executing Python code.

        Args:
            state: App state (unused)
            code: Python code to execute with ctx object and builtins

        Returns:
            Raw result dict from daemon

        Context object provides:
            - ctx.queue() - Queue state (pending, resolved count)
            - ctx.panes() - Pane state (process, bytes, actions)
            - ctx.patterns() - Pattern state (loaded patterns)
            - ctx.health() - Daemon health (running, connections, logs buffered)
            - ctx.logs(n=50) - Get last N log entries
            - ctx.raw.* - Raw access to daemon internals (queue, pane_manager, patterns, daemon)
            - ctx.log(...) - Capture output

        Examples:
            # Simple expressions (set result variable)
            debug("result = ctx.health()")
            debug("result = ctx.queue()['pending']")

            # Multi-line debugging
            debug('''
    from termtap.tmux.ops import send_keys
    from termtap.tmux._exceptions import CurrentPaneError
    try:
        send_keys("%1341", "test")
        result = "success"
    except CurrentPaneError as e:
        result = str(e)
            ''')

            # Access internals
            debug("result = list(ctx.raw.pane_manager.panes.keys())")
    """
    from ..client import DaemonClient, DaemonNotRunning

    try:
        client = DaemonClient()
        return client.debug_eval(code)
    except DaemonNotRunning:
        return {"result": None, "error": "Daemon is not running. Start with: termtap daemon start"}
