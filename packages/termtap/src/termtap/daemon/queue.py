"""Action queue for pending user requests.

PUBLIC API:
  - ActionQueue: Queue of pending actions
  - Action: Single action awaiting user response
  - ActionState: Unified state enum for action lifecycle
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

__all__ = ["ActionQueue", "Action", "ActionState"]


class ActionState(str, Enum):
    """Unified action state controlling behavior and lifecycle.

    SELECTING_PANE: User picks pane (pane_id="", no pattern matching)
    READY_CHECK: Has pane, polling patterns, match → send command → WATCHING
    WATCHING: Command sent, polling patterns, match → capture output → COMPLETED
    COMPLETED: Done with result
    CANCELLED: Aborted
    """

    SELECTING_PANE = "selecting_pane"
    READY_CHECK = "ready_check"
    WATCHING = "watching"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Action:
    """A pending user action.

    Represents an action that needs user input before completing.
    Result is stored directly in the action when resolved.
    """

    id: str
    pane_id: str  # %id or "" for pane selection
    command: str
    state: ActionState
    timestamp: float = field(default_factory=lambda: time.time())
    result: dict | None = None
    multi_select: bool = False
    pair_mode: bool = False
    linked_busy_pattern: str | None = None
    matched_ready_pattern: str | None = None
    client_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "id": self.id,
            "pane_id": self.pane_id,
            "command": self.command,
            "state": self.state.value,
            "timestamp": self.timestamp,
            "multi_select": self.multi_select,
            "pair_mode": self.pair_mode,
            "linked_busy_pattern": self.linked_busy_pattern,
            "matched_ready_pattern": self.matched_ready_pattern,
            "client_context": self.client_context,
        }


class ActionQueue:
    """Queue of pending user actions.

    Manages actions that need user input. Result is stored
    in action.result when user responds.
    """

    def __init__(self, max_size: int = 100):
        """Initialize queue.

        Args:
            max_size: Maximum number of pending actions
        """
        self.max_size = max_size
        self.pending: list[Action] = []
        self.resolved: dict[str, Action] = {}  # Track resolved for status lookup

    def add(
        self,
        pane_id: str,
        command: str,
        state: ActionState,
        multi_select: bool = False,
        client_context: dict | None = None,
    ) -> Action:
        """Add action to queue.

        Args:
            pane_id: Pane the action is for ("" for pane selection)
            command: Command that triggered the action
            state: Initial state of the action
            multi_select: Whether this is a multi-select action
            client_context: Client context (pane, session) for popup targeting

        Returns:
            Action (result will be set when resolved)

        Raises:
            RuntimeError: If queue is full
        """
        if len(self.pending) >= self.max_size:
            raise RuntimeError("Action queue full")

        action = Action(
            id=str(uuid.uuid4())[:8],
            pane_id=pane_id,
            command=command,
            state=state,
            timestamp=time.time(),
            multi_select=multi_select,
            client_context=client_context or {},
        )

        self.pending.append(action)
        return action

    def resolve(self, action_id: str, result: dict):
        """Resolve an action with user's response.

        Args:
            action_id: ID of action to resolve
            result: User's response (e.g., {"state": "ready", "patterns": [...]})
        """
        for i, action in enumerate(self.pending):
            if action.id == action_id:
                action.result = result
                action.state = ActionState.COMPLETED
                self.pending.pop(i)
                self.resolved[action_id] = action  # Keep for status lookup
                return

    def cancel(self, action_id: str, reason: str = "cancelled"):
        """Cancel an action.

        Args:
            action_id: ID of action to cancel
            reason: Reason for cancellation
        """
        for i, action in enumerate(self.pending):
            if action.id == action_id:
                action.result = {"error": reason}
                action.state = ActionState.CANCELLED
                self.pending.pop(i)
                self.resolved[action_id] = action  # Keep for status lookup
                return

    def get(self, action_id: str) -> Action | None:
        """Get action by ID.

        Args:
            action_id: ID to look up

        Returns:
            Action or None if not found
        """
        for action in self.pending:
            if action.id == action_id:
                return action
        return self.resolved.get(action_id)

    def get_next(self) -> Action | None:
        """Get next pending action.

        Returns:
            Next action or None if queue is empty
        """
        return self.pending[0] if self.pending else None

    def to_dict(self) -> list[dict]:
        """Convert queue to list of dicts for serialization.

        Returns:
            List of action dicts
        """
        return [a.to_dict() for a in self.pending]

    def __len__(self) -> int:
        return len(self.pending)

    def __bool__(self) -> bool:
        return bool(self.pending)
