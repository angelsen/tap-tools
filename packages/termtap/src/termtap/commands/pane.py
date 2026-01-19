"""Read output from tmux pane(s).

PUBLIC API:
  - pane: Read single pane with paging support (MCP tool)
  - panes: Read multiple panes with preview (MCP resource)
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ..pane import Pane
from ..tmux.resolution import validate_pane_id
from ._helpers import build_tips, build_range_info

__all__ = ["pane", "panes"]


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"inspection", "output"},
        "description": "Read single pane with paging support",
    },
)
def pane(
    state,
    pane_id: str = None,  # pyright: ignore[reportArgumentType]
    tail: int = 100,
    offset: int = None,  # pyright: ignore[reportArgumentType]
    limit: int = None,  # pyright: ignore[reportArgumentType]
) -> dict[str, Any]:
    """Read single pane with paging support.

    Args:
        state: Application state (unused).
        pane_id: Pane ID (%format). If None, prompts via Companion.
        tail: Number of lines from end (default 100, used if offset/limit not set).
        offset: Starting line number for paging (0-indexed).
        limit: Number of lines to read for paging.

    Returns:
        Markdown formatted result with pane output.
    """
    # Resolution
    resolved_pane_id: str
    if pane_id is None:
        client = DaemonClient()
        result = client.select_pane("pane")

        if result["status"] != "completed":
            return {
                "elements": [{"type": "text", "content": f"Pane selection {result['status']}"}],
                "frontmatter": {"status": result["status"]},
            }

        resolved_pane_id = result["pane"]
    else:
        resolved_pane_id = pane_id

    # Validate pane ID
    validated_pane_id = validate_pane_id(resolved_pane_id)
    if not validated_pane_id:
        return {
            "elements": [
                {
                    "type": "text",
                    "content": f"Error: Invalid pane ID format: {resolved_pane_id}. Use %id format (e.g., %42).",
                }
            ],
            "frontmatter": {"status": "error", "error": f"Invalid pane ID format: {resolved_pane_id}"},
        }

    # Touch via daemon to register intentional access (best-effort)
    try:
        client = DaemonClient()
        client.call("touch", {"pane_id": validated_pane_id})
    except Exception:
        pass  # Daemon may not be running

    try:
        # Capture using Pane abstraction
        if offset is not None and limit is not None:
            p = Pane.capture_range(validated_pane_id, offset, limit)
        else:
            p = Pane.capture_tail(validated_pane_id, tail)

        # Build response
        elements = [
            build_tips(resolved_pane_id),
        ]

        if p.content:
            elements.append({"type": "code_block", "content": p.content, "language": "text"})
        else:
            elements.append({"type": "text", "content": "(empty)"})

        elements.append(build_range_info(resolved_pane_id, p.range, p.total_lines))

        return {
            "elements": elements,
            "frontmatter": {
                "pane": resolved_pane_id,
                "status": "ok",
                "range": list(p.range),
                "total_lines": p.total_lines,
                "truncated": False,
            },
        }

    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"status": "error", "error": str(e)},
        }


@app.command(
    display="markdown",
    fastmcp={
        "type": "resource",
        "mime_type": "text/markdown",
        "tags": {"inspection", "output"},
        "description": "Read panes with preview (multi-select via Companion)",
    },
)
def panes(state) -> dict[str, Any]:
    """Read panes with preview.

    Prompts for pane selection via Companion. Smart capture:
    - Single pane: capture visible (full screen)
    - Multiple panes: 10-line preview each

    Args:
        state: Application state (unused).

    Returns:
        Markdown formatted result with pane output(s).
    """
    client = DaemonClient()
    result = client.select_panes("panes")

    if result["status"] == "error":
        return {
            "elements": [{"type": "text", "content": f"Error: {result.get('error', 'Unknown error')}"}],
            "frontmatter": {"status": "error", "error": result.get("error")},
        }

    if result["status"] != "completed":
        return {
            "elements": [{"type": "text", "content": f"Pane selection {result['status']}"}],
            "frontmatter": {"status": result["status"]},
        }

    targets = result.get("panes", [])
    if not targets:
        return {
            "elements": [{"type": "text", "content": "No panes selected"}],
            "frontmatter": {"status": "cancelled"},
        }

    # Smart capture: more lines for single, preview for multiple
    lines = 100 if len(targets) == 1 else 10

    # Build elements
    elements = []
    results = []

    for target in targets:
        validated = validate_pane_id(target)
        if not validated:
            continue

        # Touch via daemon to register intentional access (best-effort)
        try:
            client.call("touch", {"pane_id": validated})
        except Exception:
            pass  # Daemon may not be running

        try:
            p = Pane.capture_tail(validated, lines)

            # Per-pane section
            elements.append({"type": "heading", "content": target, "level": 3})
            elements.append(build_tips(target))

            if p.content:
                elements.append({"type": "code_block", "content": p.content, "language": "text"})
            else:
                elements.append({"type": "text", "content": "(empty)"})

            elements.append(build_range_info(target, p.range, p.total_lines))

            results.append(
                {
                    "pane": target,
                    "range": list(p.range),
                    "total_lines": p.total_lines,
                }
            )

        except Exception:
            continue

    return {
        "elements": elements,
        "frontmatter": {
            "panes": [r["pane"] for r in results],
            "status": "ok" if results else "error",
        },
    }
