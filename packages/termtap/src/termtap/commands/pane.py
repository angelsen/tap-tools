"""Interact with tmux panes.

PUBLIC API:
  - pane: Read and interact with target pane with caching and pagination
"""

from typing import Any

from ..app import app, DEFAULT_LINES_PER_PAGE
from ..tmux import resolve_targets_to_panes


def _build_interaction_hints(target: str) -> dict[str, str]:
    """Build interaction hint text for a pane.

    Args:
        target: The session:window.pane identifier.

    Returns:
        Dict with type and content for the hint element.
    """
    return {
        "type": "text",
        "content": f"""To interact with this pane:
- Execute: `mcp__termtap__execute(command="...", target="{target}")`
- Send: `mcp__termtap__send(message="...", target="{target}")`
- Interrupt: `mcp__termtap__interrupt(target="{target}")`
- Send keys: `mcp__termtap__send_keys(keys="...", target="{target}")`""",
    }


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
                    "termtap://pane - Interactive pane selection",
                    "termtap://pane/session1 - Read from specific pane (fresh read)",
                    "termtap://pane/session1/1 - Page 1 (most recent cached)",
                    "termtap://pane/session1/2 - Page 2 (older output)",
                    "termtap://pane/session1/-1 - Last page (oldest output)",
                ],
                "discovery": "Use termtap://ls to find available pane targets",
            }
        },
    },
)
def pane(
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
            available_panes, title="Pane Output", action="Select Panes (Tab to select, Enter to confirm)"
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
                outputs.append((swp, "[No cached content - run pane() first]"))

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

    # Format the output, then add interaction hints
    result = _format_pane_output(
        outputs,
        page=None,
        lines_per_page=DEFAULT_LINES_PER_PAGE,
        cached=False,
    )

    # Add interaction hints for each pane
    if outputs and "elements" in result:
        # Build enhanced elements with hints for each pane
        enhanced_elements = []
        i = 0

        for pane_id, swp in panes_to_read:
            # For multiple panes, there's a heading
            if len(panes_to_read) > 1:
                # Add the heading
                enhanced_elements.append(result["elements"][i])
                i += 1

            # Add interaction hints for this pane
            enhanced_elements.append(_build_interaction_hints(swp))
            enhanced_elements.append({"type": "text", "content": ""})

            # Add the code block with output
            enhanced_elements.append(result["elements"][i])
            i += 1

        result["elements"] = enhanced_elements

    return result
