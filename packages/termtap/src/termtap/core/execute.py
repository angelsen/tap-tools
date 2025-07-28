"""Core execution - simplified.

This module now only exports ExecutorState for stream management.
The actual execution logic lives in commands/bash.py
"""

from dataclasses import dataclass, field
from ..tmux.stream import _StreamManager


@dataclass
class ExecutorState:
    """State container for stream management across executions.

    Attributes:
        stream_manager: Manager for tmux pane streams.
    """

    stream_manager: _StreamManager = field(default_factory=_StreamManager)
