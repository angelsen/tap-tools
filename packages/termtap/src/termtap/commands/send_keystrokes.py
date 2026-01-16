"""Send raw keystrokes to tmux panes.

PUBLIC API:
  - send_keystrokes: Send keystrokes to pane
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ..tmux.ops import send_keys
from ._helpers import _require_pane_id, build_hint


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
def send_keystrokes(state, keys: list[str], pane_id: str = None) -> dict[str, Any]:  # pyright: ignore[reportArgumentType]
    """Send raw keystrokes to target pane.

    Each keystroke in the list is sent individually. Special keys like Enter, Escape, C-c are supported.

    Args:
        state: Application state (unused).
        keys: List of keystrokes (e.g., ["q"], ["Down", "Enter"], ["C-c"]).
        pane_id: Pane ID (%format).

    Returns:
        Markdown formatted result with keystroke sending status.

    Examples:
        send_keystrokes(["q"])                           # Just q (exit less)
        send_keystrokes(["y", "Enter"])                  # y followed by Enter
        send_keystrokes(["Down", "Down", "Enter"])       # Navigate and select
        send_keystrokes(["C-c"])                         # Send Ctrl+C
        send_keystrokes(["Escape", ":q", "Enter"])       # Exit vim
    """
    client = DaemonClient()

    try:
        resolved_pane_id = _require_pane_id(client, "send_keystrokes", pane_id)
    except ValueError as e:
        return {"elements": [{"type": "text", "content": str(e)}]}

    if not keys:
        return {
            "elements": [{"type": "text", "content": "Error: No keys to send"}],
            "frontmatter": {"status": "error", "error": "No keys to send"},
        }

    try:
        from ..types import LineEnding

        success = send_keys(resolved_pane_id, *keys, line_ending=LineEnding.NONE)

        keys_display = " ".join(keys)
        if len(keys_display) > 40:
            keys_display = keys_display[:37] + "..."

        if success:
            return {
                "elements": [
                    {"type": "text", "content": f"Sent **{len(keys)}** keystroke(s) to **{resolved_pane_id}**"},
                    {"type": "code_block", "content": " ".join(keys), "language": ""},
                    build_hint(resolved_pane_id),
                ],
                "frontmatter": {
                    "keys": keys_display,
                    "pane": resolved_pane_id,
                    "status": "sent",
                },
            }
        else:
            return {
                "elements": [{"type": "text", "content": f"Failed to send keystrokes to {resolved_pane_id}"}],
                "frontmatter": {"status": "failed", "pane": resolved_pane_id},
            }

    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"status": "error", "error": str(e)},
        }
