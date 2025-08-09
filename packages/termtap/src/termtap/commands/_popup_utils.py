"""Popup utilities for termtap commands.

Internal utilities for pane selection in termtap commands.
"""

from typing import List, Optional

from ..popup import Popup
from ..popup.gum import GumStyle, GumFilter


def _format_pane_for_selection(pane_info: dict) -> str:
    """Format pane information for display in selection list.

    Args:
        pane_info: Dict with Pane, Shell, Process, State keys.

    Returns:
        Formatted string for display.
    """
    pane_id = pane_info.get("Pane", "").ljust(25)
    shell = (pane_info.get("Shell") or "None").ljust(8)
    process = (pane_info.get("Process") or "None").ljust(15)
    state = pane_info.get("State", "unknown")

    return f"{pane_id}{shell}{process}{state}"


def _select_single_pane(
    panes: List[dict],
    title: str = "Select Pane",
    action: str = "Choose Target Pane"
) -> Optional[str]:
    """Select a single pane using fuzzy filtering with styled popup.

    Args:
        panes: List of pane info dicts.
        title: Tmux window title.
        action: Header action text.

    Returns:
        Selected pane ID or None if cancelled.
    """
    if not panes:
        return None

    options = [
        (pane_info.get("Pane", ""), _format_pane_for_selection(pane_info))
        for pane_info in panes
    ]
    popup = Popup(title=title, width="65")
    selected = popup.add(
        GumStyle(action, header=True),
        "Select the target pane for command execution:",
        "",
        GumFilter(
            options=options,
            placeholder="Type to search panes...",
            fuzzy=True,
            limit=1
        )
    ).show()

    return selected if selected else None


def _select_multiple_panes(
    panes: List[dict],
    title: str = "Select Panes",
    action: str = "Choose Target Panes"
) -> List[str]:
    """Select multiple panes using fuzzy filtering with styled popup.

    Args:
        panes: List of pane info dicts.
        title: Tmux window title.
        action: Header action text.

    Returns:
        List of selected pane IDs.
    """
    if not panes:
        return []

    options = [
        (pane_info.get("Pane", ""), _format_pane_for_selection(pane_info))
        for pane_info in panes
    ]
    popup = Popup(title=title, width="65")
    selected = popup.add(
        GumStyle(action, header=True),
        "Select panes to read from:",
        "Use space/tab to select multiple, Enter to confirm",
        "",
        GumFilter(
            options=options,
            placeholder="Type to search, space to select multiple...",
            fuzzy=True,
            limit=0
        )
    ).show()

    return selected if isinstance(selected, list) else []