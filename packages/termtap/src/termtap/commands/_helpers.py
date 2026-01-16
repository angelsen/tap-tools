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
        pane_id: Pane identifier (%id format)

    Returns:
        Markdown text element with interaction tips
    """
    return {
        "type": "text",
        "content": f"""**Next steps:**
- Execute: `mcp__termtap__execute(command="...", pane_id="{pane_id}")`
- Send keys: `mcp__termtap__send_keystrokes(keys=["..."], pane_id="{pane_id}")`
- Interrupt: `mcp__termtap__interrupt(pane_id="{pane_id}")`
- Page: `mcp__termtap__pane(pane_id="{pane_id}", offset=N, limit=M)`""",
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
        "content": f'Use `mcp__termtap__pane(pane_id="{pane_id}")` to see result',
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
        "content": f'Lines {start}-{end} of {total} | `mcp__termtap__pane(pane_id="{pane_id}")` for more',
    }


def _require_pane_id(client: Any, command_name: str, pane_id: str | None) -> str:
    """Get pane ID, triggering selection if needed.

    Args:
        client: DaemonClient instance
        command_name: Name of command that needs pane ID
        pane_id: Optional pane identifier (%format)

    Returns:
        Validated pane ID

    Raises:
        ValueError: If pane selection fails or is cancelled
    """
    if pane_id:
        return pane_id

    result = client.select_pane(command_name)

    if result["status"] == "completed":
        return result["pane"]

    if result["status"] == "timeout":
        raise ValueError("Pane selection timed out. Run 'termtap companion' to respond.")

    raise ValueError(f"Pane selection {result['status']}")
