"""Shared helper functions for commands.

PUBLIC API:
  - build_tips: Build per-pane interaction tips for markdown output
  - build_hint: Build "check output" hint for action commands
  - build_range_info: Build range info blockquote for output commands
"""

from typing import Any

__all__ = ["build_tips", "build_hint", "build_range_info"]


def build_tips(pane_id: str) -> dict[str, str]:
    """Build per-pane interaction tips.

    Args:
        pane_id: Pane identifier (in %id or session:window.pane format)

    Returns:
        Markdown text element with interaction tips
    """
    return {
        "type": "text",
        "content": f"""**Tips:**
- Execute: `execute(command="...", target="{pane_id}")`
- Send keys: `send_keystrokes(keys=[...], target="{pane_id}")`
- Interrupt: `interrupt(target="{pane_id}")`
- Read more: `pane(target="{pane_id}")`""",
    }


def build_hint(pane_id: str) -> dict[str, str]:
    """Build "check output" hint for action commands.

    Args:
        pane_id: Pane identifier

    Returns:
        Markdown blockquote element with hint
    """
    return {
        "type": "blockquote",
        "content": f'Use `pane(target="{pane_id}")` to see result',
    }


def build_range_info(pane_id: str, range_: tuple[int, int], total: int) -> dict[str, str]:
    """Build range info blockquote for output commands.

    Args:
        pane_id: Pane identifier
        range_: (start, end) line numbers
        total: Total lines in buffer

    Returns:
        Markdown blockquote element with range info
    """
    start, end = range_
    return {
        "type": "blockquote",
        "content": f'Lines {start}-{end} of {total} | `pane(target="{pane_id}")` for more',
    }


def _require_target(
    client: Any, command_name: str, target: str | None
) -> tuple[str, None] | tuple[None, dict[str, Any]]:
    """Get target, triggering selection if needed.

    Args:
        client: DaemonClient instance
        command_name: Name of command that needs target
        target: Optional target pane identifier

    Returns:
        (target, None) on success
        (None, error_response) on failure
    """
    if target:
        return target, None

    result = client.select_pane(command_name)

    if result["status"] == "completed":
        return result["pane"], None

    if result["status"] == "timeout":
        return None, {
            "elements": [{"type": "text", "content": "Pane selection timed out. Run 'termtap companion' to respond."}],
            "frontmatter": {"status": "timeout"},
        }

    return None, {
        "elements": [{"type": "text", "content": f"Pane selection {result['status']}"}],
        "frontmatter": {"status": result["status"]},
    }
