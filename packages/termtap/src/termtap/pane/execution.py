"""Command execution for panes."""

from typing import Optional, Any

from .core import Pane


def send_command(pane: Pane, command: str, wait: bool = False, timeout: Optional[float] = None) -> dict[str, Any]:
    """Send command to pane with handler lifecycle.

    Minimal version for testing - implements just send, no waiting logic yet.

    Args:
        pane: The target pane
        command: Command to execute
        wait: Whether to wait for completion (not implemented yet)
        timeout: Override timeout (not used yet)

    Returns:
        Dict with status and command
    """
    # Handler lifecycle - before_send
    modified_command = pane.handler.before_send(pane, command)
    if modified_command is None:
        return {"error": "Command cancelled by handler", "status": "cancelled"}

    # Send command
    from ..tmux.pane import send_keys, send_via_paste_buffer

    if "\n" in modified_command:
        send_via_paste_buffer(pane.pane_id, modified_command)
    else:
        send_keys(pane.pane_id, modified_command)

    # Handler lifecycle - after_send
    pane.handler.after_send(pane, modified_command)

    # For now, just return success
    return {"status": "sent", "command": modified_command, "pane": pane.session_window_pane}


def interrupt(pane: Pane) -> bool:
    """Send interrupt signal to pane.

    Returns:
        True if successful
    """
    success, _ = pane.handler.interrupt(pane)
    return success
