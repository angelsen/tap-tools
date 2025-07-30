"""Stream management for panes."""

from .core import Pane


def get_stream(pane: Pane):
    """Get or create stream for pane."""
    # For now, streaming requires the command context
    # This will be used when we implement wait logic in execution.py
    raise NotImplementedError("Streaming will be implemented when needed for wait logic")


def mark_command(stream, cmd_id: str, command: str) -> None:
    """Mark command start in stream."""
    stream.mark_command(cmd_id, command)


def mark_command_end(stream, cmd_id: str) -> None:
    """Mark command end in stream."""
    stream.mark_command_end(cmd_id)


def read_command_output(stream, cmd_id: str, as_displayed: bool = False) -> str:
    """Read output for specific command."""
    return stream.read_command_output(cmd_id, as_displayed=as_displayed)
