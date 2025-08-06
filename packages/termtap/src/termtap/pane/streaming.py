"""Pane-centric streaming - wraps tmux Stream for easy pane operations.

PUBLIC API:
  - ensure_streaming: Start streaming for pane if not already active
  - mark_command_start: Mark beginning of command execution
  - mark_command_end: Mark end of command execution
  - get_command_output: Get output for specific command
  - read_command_output: Read output for specific command
  - read_since_last: Read new output since last read
  - read_recent: Read recent output with line limit
"""

import time
from pathlib import Path
from .core import Pane
from ..tmux.stream import Stream

# Default stream directory
STREAM_DIR = Path("/tmp/termtap/streams")


def get_stream(pane: Pane, stream_dir: Path = STREAM_DIR) -> Stream:
    """Get stream for pane - creates new instance each time.

    No global state - each Stream instance coordinates through files.
    """
    return Stream(pane.pane_id, pane.session_window_pane, stream_dir)


def ensure_streaming(pane: Pane) -> bool:
    """Ensure pane is streaming to file."""
    stream = get_stream(pane)
    if stream.is_active():
        return True
    return stream.start()


def mark_command_start(pane: Pane, command: str) -> str:
    """Mark command start position and return command ID.

    Args:
        pane: Target pane
        command: Command being executed

    Returns:
        Command ID for tracking
    """
    stream = get_stream(pane)
    cmd_id = f"cmd_{int(time.time() * 1000)}"
    stream.mark_command(cmd_id, command)
    return cmd_id


def mark_command_end(pane: Pane, cmd_id: str) -> None:
    """Mark command end position.

    Args:
        pane: Target pane
        cmd_id: Command ID from mark_command_start
    """
    stream = get_stream(pane)
    stream.mark_command_end(cmd_id)


def get_command_output(pane: Pane, cmd_id: str, as_displayed: bool = True) -> str:
    """Get output for specific command.

    Args:
        pane: Target pane
        cmd_id: Command ID from mark_command_start
        as_displayed: Whether to render ANSI (default True)

    Returns:
        Command output
    """
    stream = get_stream(pane)
    return stream.read_command_output(cmd_id, as_displayed)


def read_command_output(pane: Pane, cmd_id: str, as_displayed: bool = True) -> str:
    """Read output for specific command (alias for get_command_output)."""
    return get_command_output(pane, cmd_id, as_displayed)


def read_since_last(pane: Pane, as_displayed: bool = True) -> str:
    """Read new output since last user read."""
    stream = get_stream(pane)
    output = stream.read_since_user_last(as_displayed)
    stream.mark_user_read()
    return output


def read_recent(pane: Pane, lines: int = 50, as_displayed: bool = True) -> str:
    """Read recent lines from stream."""
    stream = get_stream(pane)
    return stream.read_last_lines(lines, as_displayed)
