"""Internal popup utilities for termtap commands."""

from typing import List, Optional

from tmux_popup import Popup, Canvas, Markdown, Filter, Input


def _format_pane_for_selection(pane_info: dict) -> str:
    """Format pane information for display in selection list.

    Args:
        pane_info: Dict with Pane, Shell, Process, State keys.

    Returns:
        Formatted string for display.
    """
    pane_id = pane_info.get("Pane", "").ljust(20)
    shell = (pane_info.get("Shell") or "None").ljust(10)
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

    # Create dict options: {display: pane_id}
    options = {_format_pane_for_selection(pane_info): pane_info.get("Pane", "") for pane_info in panes}

    popup = Popup(width="65")
    canvas = Canvas()
    canvas.add(
        Markdown(f"""# {action}

Select the target pane for command execution:""")
    )
    popup.add(canvas)

    # Single selection returns string directly
    selected = popup.add(
        Filter(options=options, placeholder="Type to search panes...", fuzzy=True, no_limit=False)
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

    # Create dict options: {display: pane_id}
    options = {_format_pane_for_selection(pane_info): pane_info.get("Pane", "") for pane_info in panes}

    popup = Popup(width="65")
    canvas = Canvas()
    canvas.add(
        Markdown(f"""# {action}

Select panes to read from:
Use Tab to select multiple, Enter to confirm""")
    )
    popup.add(canvas)

    # Multi-selection returns list directly
    selected = popup.add(
        Filter(options=options, placeholder="Type to search, Tab to select multiple...", fuzzy=True, no_limit=True)
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
        # Create dict options: {display: pane_id}
        options = {_format_pane_for_selection(pane_info): pane_info.get("Pane", "") for pane_info in panes}

        popup = Popup(width="65")
        canvas = Canvas()
        canvas.add(
            Markdown(f"""# {action}

Select the target pane for command execution:""")
        )
        popup.add(canvas)

        # Single selection returns string directly
        selected = popup.add(
            Filter(options=options, placeholder="Type to search panes...", fuzzy=True, no_limit=False)
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
        popup = Popup(width="65")
        canvas = Canvas()
        canvas.add(
            Markdown("""# Create New Session

No pane selected. Enter name for new session:""")
        )
        popup.add(canvas)

        session_name = popup.add(Input(value=generated_name, placeholder="Session name...", prompt="Name: ")).show()

        if session_name:
            try:
                pane_id, swp = resolve_or_create_target(session_name)
                return (pane_id, swp)
            except RuntimeError:
                return None

    return None
