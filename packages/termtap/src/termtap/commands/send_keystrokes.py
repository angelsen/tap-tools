"""Send raw keystrokes to tmux panes for interactive programs.

PUBLIC API:
  - send_keystrokes: Send raw keystrokes to target pane
"""

from typing import Any

from ..app import app
from ..pane import Pane, send_keys as pane_send_keys
from ..tmux import resolve_target_to_pane


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"input", "control"},
        "description": """Send individual keystrokes to tmux pane for controlling interactive programs.

Use this for:
- Navigating menus and interfaces (arrow keys, Enter, Tab)
- Exiting programs (q for less, Escape :q Enter for vim)
- Sending control sequences (Ctrl+C, Ctrl+D, Ctrl+Z)
- Interacting with prompts (y/n confirmations)

NOT for running shell commands - use 'execute' for commands instead.""",
    },
)
def send_keystrokes(state, keys: list[str], target: str = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Send raw keystrokes to target pane.

    Each keystroke in the list is sent individually. Special keys like Enter, Escape, C-c are supported.

    Args:
        state: Application state (unused).
        keys: List of keystrokes to send (e.g., ["q"], ["Down", "Down", "Enter"], ["C-c"]).
        target: Target pane identifier. None for interactive selection.

    Returns:
        Markdown formatted result with keystroke sending status.

    Examples:
        send_keystrokes(["q"])                           # Just q (exit less)
        send_keystrokes(["y", "Enter"])                  # y followed by Enter
        send_keystrokes(["Down", "Down", "Enter"])       # Navigate and select
        send_keystrokes(["C-c"])                         # Send Ctrl+C
        send_keystrokes(["Escape", ":q", "Enter"])       # Exit vim
        send_keystrokes(["Hello", "Enter", "World"])     # Type text with newline
    """
    if target is None:
        from ._popup_utils import _select_single_pane
        from .ls import ls

        available_panes = ls(state)
        target = _select_single_pane(
            available_panes, title="Send Keystrokes", action="Choose Target Pane for Keystroke Input"
        )

        if not target:
            return {
                "elements": [{"type": "text", "content": "Operation cancelled"}],
                "frontmatter": {"status": "cancelled"},
            }

    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    pane = Pane(pane_id)

    # Join the list of keystrokes with spaces for the underlying pane_send_keys function
    keys_string = " ".join(keys)
    result = pane_send_keys(pane, keys_string)

    elements = []

    if result["output"]:
        elements.append({"type": "code_block", "content": result["output"], "language": result["language"]})

    if result["status"] == "failed":
        elements.append(
            {"type": "blockquote", "content": f"Failed to send keystrokes: {result.get('error', 'Unknown error')}"}
        )

    return {
        "elements": elements,
        "frontmatter": {
            "keys": keys_string[:40] + ("..." if len(keys_string) > 40 else ""),
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        },
    }
