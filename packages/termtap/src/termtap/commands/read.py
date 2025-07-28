"""Read command - clean pane output reading."""

from typing import Any

from ..app import app
from ..types import Target, ReadMode
from ..tmux import capture_visible, capture_all, capture_last_n
from ..tmux.utils import resolve_target_to_pane
from ..process.detector import detect_process


@app.command(
    display="markdown",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux pane",
        "uri": "bash://{target}/{lines}",
    },
)
def read(
    state,
    target: Target = "default",
    lines: int | None = None,
    mode: ReadMode = "direct",
) -> dict[str, Any]:
    """Read output from target pane."""
    # 1. Resolve target
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"target": target, "error": str(e)},
        }

    # 2. Read content based on mode
    if mode == "stream":
        stream = state.executor.stream_manager.get_stream(pane_id, session_window_pane)

        # Start stream if needed
        # Use is_active() which checks sync state, not just file existence
        if not stream.is_active() and not stream.is_running():
            stream.start()
            content = "[Stream starting - no content yet]"
            lines_read = 0
        else:
            content = stream.read_since_user_last()
            stream.mark_user_read()
            lines_read = len(content.splitlines()) if content else 0
    else:
        # Direct tmux capture
        if lines == -1:
            content = capture_all(pane_id)
        elif lines:
            content = capture_last_n(pane_id, lines)
        else:
            content = capture_visible(pane_id)

        lines_read = len(content.splitlines()) if content else 0

    # 3. Detect process for syntax highlighting
    info = detect_process(pane_id)
    process = info.process or info.shell

    # 4. Build markdown response
    elements = []

    # Main content in code block
    elements.append({"type": "code_block", "content": content or "[No output]", "language": process})

    # Status info for stream mode
    if mode == "stream":
        elements.append({"type": "text", "content": f"Stream mode: {lines_read} new lines"})

    return {
        "elements": elements,
        "frontmatter": {"pane": session_window_pane, "process": process, "lines": lines_read, "mode": mode},
    }
