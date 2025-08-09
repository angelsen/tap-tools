"""Popup utilities for termtap commands."""

from typing import List, Optional

from ..popup import Popup, Theme


def create_command_popup(title: str, action: str) -> Popup:
    """Create a consistently styled popup for command operations.

    Args:
        title: Tmux window title (e.g., pane name or context).
        action: Action being performed (header text).

    Returns:
        Configured Popup instance with consistent theming.
    """
    theme = Theme(
        header="--bold --foreground 14 --border rounded --align center --width 61"
    )
    
    popup = Popup(
        title=title,
        theme=theme,
        width="65"
    )
    
    popup.header(action)
    
    return popup


def format_pane_for_selection(pane_info: dict) -> str:
    """Format pane information for display in selection list.

    Args:
        pane_info: Dict with Pane, Shell, Process, State keys from ls command.

    Returns:
        Formatted string with aligned columns.
    """
    pane_id = pane_info.get("Pane", "").ljust(25)
    shell = (pane_info.get("Shell") or "None").ljust(8)
    process = (pane_info.get("Process") or "None").ljust(15)
    state = pane_info.get("State", "unknown")
    
    return f"{pane_id}{shell}{process}{state}"


def select_single_pane(
    panes: List[dict], 
    title: str = "Select Pane", 
    action: str = "Choose Target Pane"
) -> Optional[str]:
    """Select a single pane using fuzzy filtering with styled popup.

    Args:
        panes: List of pane info dicts from ls command.
        title: Tmux window title. Defaults to "Select Pane".
        action: Header action text. Defaults to "Choose Target Pane".

    Returns:
        Selected pane ID or None if cancelled.
    """
    if not panes:
        return None
    
    # Create styled popup
    popup = create_command_popup(title, action)
    popup.text("Select the target pane for command execution:")
    popup.text("")
    
    # Value is pane ID, display is formatted string
    options = [
        (pane_info.get("Pane", ""), format_pane_for_selection(pane_info))
        for pane_info in panes
    ]
    
    selected = popup.filter(
        options=options,
        placeholder="Type to search panes...",
        limit=1,  # Single selection
        fuzzy=True
    )
    
    popup.cleanup()
    # Returns str when limit=1
    assert isinstance(selected, str)
    return selected if selected else None


def select_multiple_panes(
    panes: List[dict], 
    title: str = "Select Panes", 
    action: str = "Choose Target Panes"
) -> List[str]:
    """Select multiple panes using fuzzy filtering with styled popup.

    Args:
        panes: List of pane info dicts from ls command.
        title: Tmux window title. Defaults to "Select Panes".
        action: Header action text. Defaults to "Choose Target Panes".

    Returns:
        List of selected pane IDs (empty if cancelled).
    """
    if not panes:
        return []
    
    # Create styled popup
    popup = create_command_popup(title, action)
    popup.text("Select panes to read from:")
    popup.text("Use space/tab to select multiple, Enter to confirm")
    popup.text("")
    options = [
        (pane_info.get("Pane", ""), format_pane_for_selection(pane_info))
        for pane_info in panes
    ]
    
    selected = popup.filter(
        options=options,
        placeholder="Type to search, space to select multiple...",
        limit=0,  # Unlimited selections
        fuzzy=True
    )
    
    popup.cleanup()
    return selected if isinstance(selected, list) else []