"""Internal popup utilities for termtap commands."""

from typing import List, Optional

from tmux_popup import Popup
from tmux_popup.gum import GumStyle, GumFilter, GumInput


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
    panes: List[dict], title: str = "Select Pane", action: str = "Choose Target Pane"
) -> Optional[str]:
    """Select a single pane using fuzzy filtering with styled popup.

    Args:
        panes: List of pane info dicts.
        title: Tmux window title. Defaults to 'Select Pane'.
        action: Header action text. Defaults to 'Choose Target Pane'.

    Returns:
        Selected pane ID or None if cancelled.
    """
    if not panes:
        return None

    options = [(pane_info.get("Pane", ""), _format_pane_for_selection(pane_info)) for pane_info in panes]
    popup = Popup(title=title, width="65")
    selected = popup.add(
        GumStyle(action, header=True),
        "Select the target pane for command execution:",
        "",
        GumFilter(options=options, placeholder="Type to search panes...", fuzzy=True, limit=1),
    ).show()

    return selected if selected else None


def _select_multiple_panes(
    panes: List[dict], title: str = "Select Panes", action: str = "Choose Target Panes"
) -> List[str]:
    """Select multiple panes using fuzzy filtering with styled popup.

    Args:
        panes: List of pane info dicts.
        title: Tmux window title. Defaults to 'Select Panes'.
        action: Header action text. Defaults to 'Choose Target Panes'.

    Returns:
        List of selected pane IDs.
    """
    if not panes:
        return []

    options = [(pane_info.get("Pane", ""), _format_pane_for_selection(pane_info)) for pane_info in panes]
    popup = Popup(title=title, width="65")
    selected = popup.add(
        GumStyle(action, header=True),
        "Select panes to read from:",
        "Use space/tab to select multiple, Enter to confirm",
        "",
        GumFilter(options=options, placeholder="Type to search, space to select multiple...", fuzzy=True, limit=0),
    ).show()

    return selected if isinstance(selected, list) else []


def _select_or_create_pane(
    panes: List[dict], title: str = "Select Pane", action: str = "Choose Target Pane", allow_create: bool = True
) -> Optional[tuple[str, str]]:
    """Select a single pane or create a new session.

    Args:
        panes: List of pane info dicts.
        title: Tmux window title. Defaults to 'Select Pane'.
        action: Header action text. Defaults to 'Choose Target Pane'.
        allow_create: Whether to offer session creation if no selection. Defaults to True.

    Returns:
        Tuple of (pane_id, session_window_pane) or None if cancelled.
    """
    if panes:
        options = [(pane_info.get("Pane", ""), _format_pane_for_selection(pane_info)) for pane_info in panes]
        popup = Popup(title=title, width="65")
        selected = popup.add(
            GumStyle(action, header=True),
            "Select the target pane for command execution:",
            "",
            GumFilter(options=options, placeholder="Type to search panes...", fuzzy=True, limit=1),
        ).show()

        if selected:
            from ..tmux import resolve_target_to_pane

            try:
                pane_id, swp = resolve_target_to_pane(selected)
                return (pane_id, swp)
            except RuntimeError:
                return None
    if allow_create:
        from ..tmux.names import _generate_session_name
        from ..tmux import resolve_or_create_target

        generated_name = _generate_session_name()
        popup = Popup(title="Create Session", width="50")
        session_name = popup.add(
            GumStyle("Create New Session", header=True),
            "No pane selected. Enter name for new session:",
            "",
            GumInput(value=generated_name, placeholder="Session name...", prompt="Name: "),
        ).show()

        if session_name:
            try:
                pane_id, swp = resolve_or_create_target(session_name)
                return (pane_id, swp)
            except RuntimeError:
                return None

    return None
