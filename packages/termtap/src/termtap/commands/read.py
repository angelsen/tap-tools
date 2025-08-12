"""Read output from tmux panes.

PUBLIC API:
  - read: Read output from target pane with caching and pagination
"""

from typing import Any

from ..app import app, DEFAULT_LINES_PER_PAGE
from ..tmux import resolve_targets_to_panes


@app.command(
    display="markdown",
    fastmcp={
        "type": "resource",
        "mime_type": "text/markdown",
        "tags": {"inspection", "output"},
        "description": "Read output from tmux pane with pagination",
        "stub": {
            "response": {
                "description": "Read output from tmux pane with optional pagination",
                "usage": [
                    "termtap://read - Interactive pane selection",
                    "termtap://read/session1 - Read from specific pane (fresh read)",
                    "termtap://read/session1/1 - Page 1 (most recent cached)",
                    "termtap://read/session1/2 - Page 2 (older output)",
                    "termtap://read/session1/-1 - Last page (oldest output)",
                ],
                "discovery": "Use termtap://ls to find available pane targets",
            }
        },
    },
)
def read(
    state,
    target: list = None,  # type: ignore[assignment]
    page: int = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Read full pane buffer with caching and pagination.

    Args:
        state: Application state with read_cache.
        target: List of target panes. None for interactive selection.
        page: Page number for pagination. None for fresh read, 1+ for pages (1-based), -1 for oldest.

    Returns:
        Markdown formatted result with pane output(s).
    """
    from ._cache_utils import _format_pane_output

    if target is None:
        from ._popup_utils import _select_multiple_panes
        from .ls import ls

        available_panes = ls(state)
        if not available_panes:
            return {
                "elements": [{"type": "text", "content": "Error: No panes available"}],
                "frontmatter": {"error": "No panes available", "status": "error"},
            }

        selected_pane_ids = _select_multiple_panes(
            available_panes, title="Read Output", action="Select Panes to Read From (space to select, enter to confirm)"
        )

        if not selected_pane_ids:
            return {
                "elements": [{"type": "text", "content": "Error: No panes selected"}],
                "frontmatter": {"error": "No panes selected", "status": "error"},
            }

        targets_to_resolve = selected_pane_ids
    else:
        targets_to_resolve = target

    try:
        panes_to_read = resolve_targets_to_panes(targets_to_resolve)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    if not panes_to_read:
        return {
            "elements": [{"type": "text", "content": "Error: No panes found for target(s)"}],
            "frontmatter": {"error": "No panes found", "status": "error"},
        }

    # Use cached content when page is specified
    if page is not None:
        outputs = []
        for pane_id, swp in panes_to_read:
            if swp in state.read_cache:
                cache = state.read_cache[swp]
                outputs.append((swp, cache.content))
            else:
                outputs.append((swp, "[No cached content - run read() first]"))

        cache_time = 0.0
        if outputs and panes_to_read[0][1] in state.read_cache:
            cache_time = state.read_cache[panes_to_read[0][1]].timestamp

        return _format_pane_output(
            outputs, page=page, lines_per_page=DEFAULT_LINES_PER_PAGE, cached=True, cache_time=cache_time
        )

    # Fresh read when page is None
    from ..pane import Pane, process_scan

    outputs = []
    for pane_id, swp in panes_to_read:
        with process_scan(pane_id):
            pane = Pane(pane_id)
            output = pane.handler.capture_output(pane, state=state)

        if swp in state.read_cache:
            full_content = state.read_cache[swp].content
        else:
            full_content = output

        outputs.append((swp, full_content))

    return _format_pane_output(
        outputs,
        page=None,
        lines_per_page=DEFAULT_LINES_PER_PAGE,
        cached=False,
    )
