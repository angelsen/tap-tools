"""Connection state machine using transitions library.

PUBLIC API:
  - ConnectionState: Enum of connection lifecycle states
  - ConnectionMachine: Thread-safe state machine for connection management
"""

from enum import Enum
from typing import Any

from transitions.extensions import LockedMachine


class ConnectionState(str, Enum):
    """Connection lifecycle states.

    Attributes:
        DISCONNECTED: Not connected to any Chrome page
        CONNECTING: Connection in progress
        CONNECTED: Connected and ready for operations
        INSPECTING: Element selection mode active
        DISCONNECTING: Cleanup in progress
    """

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INSPECTING = "inspecting"
    DISCONNECTING = "disconnecting"


class ConnectionMachine(LockedMachine):  # type: ignore
    """Thread-safe state machine for WebTap connection lifecycle.

    States:
        - disconnected: Not connected to any Chrome page
        - connecting: Connection in progress
        - connected: Connected and ready for operations
        - inspecting: Element selection mode active
        - disconnecting: Cleanup in progress

    The machine uses LockedMachine for thread safety and queued transitions.
    Epoch counter is incremented on successful connection.
    """

    def __init__(self):
        """Initialize the connection state machine."""
        _states = [s.value for s in ConnectionState]
        _transitions: list[dict[str, Any]] = [
            {"trigger": "start_connect", "source": ["disconnected", "connected", "inspecting"], "dest": "connecting"},
            {
                "trigger": "connect_success",
                "source": "connecting",
                "dest": "connected",
                "after": "_increment_epoch",
            },
            {"trigger": "connect_failed", "source": "connecting", "dest": "disconnected"},
            {"trigger": "start_inspect", "source": "connected", "dest": "inspecting"},
            {"trigger": "stop_inspect", "source": "inspecting", "dest": "connected"},
            {
                "trigger": "start_disconnect",
                "source": ["connected", "inspecting"],
                "dest": "disconnecting",
            },
            {
                "trigger": "disconnect_complete",
                "source": ["disconnecting", "connecting"],
                "dest": "disconnected",
            },
            {"trigger": "force_disconnect", "source": "*", "dest": "disconnected"},
        ]

        super().__init__(
            states=_states,
            transitions=_transitions,
            initial="disconnected",
            auto_transitions=False,
            queued=True,
        )
        self.epoch = 0

    def _increment_epoch(self):
        """Increment epoch counter on successful connection."""
        self.epoch += 1
