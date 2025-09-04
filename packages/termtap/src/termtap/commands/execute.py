"""Execute commands in tmux panes.

PUBLIC API:
  - execute: Execute command in target pane with output caching
"""

from typing import Any

from ..app import app, DEFAULT_LINES_PER_PAGE
from ..pane import Pane, send_command
from ..tmux import resolve_or_create_target


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"execution", "shell"},
        "description": "Execute command in any shell or REPL within tmux pane",
        "aliases": [
            {
                "name": "send",
                "description": "Send a message to the target pane",
                "param_mapping": {"command": "message"},
            }
        ],
    },
)
def execute(
    state,
    command: str,
    target: str = None,  # type: ignore[assignment]
    wait: bool = True,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Execute command in target pane with output caching.

    Args:
        state: Application state with read_cache for output caching.
        command: Command to execute.
        target: Target pane identifier. None for interactive selection.
        wait: Whether to wait for command completion. Defaults to True.
        timeout: Command timeout in seconds. 0 means no timeout.

    Returns:
        Markdown formatted result with command output and metadata.
        Full output is cached, but only last 50 lines are displayed.
    """
    if target is None:
        from ._popup_utils import _select_or_create_pane
        from .ls import ls

        available_panes = ls(state)
        result = _select_or_create_pane(
            available_panes, title="Execute Command", action="Choose Target Pane for Command Execution"
        )

        if not result:
            return {
                "elements": [{"type": "text", "content": "Operation cancelled"}],
                "frontmatter": {"status": "cancelled"},
            }

        pane_id, session_window_pane = result
    else:
        try:
            pane_id, session_window_pane = resolve_or_create_target(target)
        except RuntimeError as e:
            return {
                "elements": [{"type": "text", "content": f"Error: {e}"}],
                "frontmatter": {"error": str(e), "status": "error"},
            }

    from ._cache_utils import _build_frontmatter, _truncate_command

    pane = Pane(pane_id)
    result = send_command(pane, command, wait=wait, timeout=timeout, state=state)

    # Handler already cached, use returned data for display
    displayed_output = result["output"]
    lines = displayed_output.splitlines() if displayed_output else []
    lines_shown = len(lines)

    truncated = False
    if session_window_pane in state.read_cache:
        cache = state.read_cache[session_window_pane]
        full_lines = cache.content.splitlines()
        truncated = len(full_lines) > DEFAULT_LINES_PER_PAGE

    elements = []

    # Add "read more" hint if output is truncated
    code_content = displayed_output
    if truncated and displayed_output:
        hint = f'... read more with readMcpResource("termtap://pane/{session_window_pane}/2", "termtap")\n'
        code_content = hint + displayed_output

    if code_content:
        elements.append({"type": "code_block", "content": code_content, "language": result["language"]})

    if result["status"] == "timeout":
        elements.append({"type": "blockquote", "content": f"Command timed out after {result['elapsed']:.1f}s"})

    total_lines = lines_shown
    cache_time = None
    if session_window_pane in state.read_cache:
        cache = state.read_cache[session_window_pane]
        total_lines = len(cache.content.splitlines())
        cache_time = cache.timestamp

    return {
        "elements": elements,
        "frontmatter": _build_frontmatter(
            target=session_window_pane,
            lines_shown=lines_shown,
            total_lines=total_lines,
            cached=bool(cache_time),
            cache_time=cache_time,
            command=_truncate_command(result["command"]),
            status=result["status"],
            elapsed=round(result["elapsed"], 2),
            truncated=truncated,
        ),
    }
