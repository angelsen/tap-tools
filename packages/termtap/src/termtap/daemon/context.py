"""Daemon context for RPC handlers.

PUBLIC API:
  - DaemonContext: Shared daemon dependencies for RPC handlers
"""

from dataclasses import dataclass
from typing import Any

__all__ = ["DaemonContext"]


@dataclass
class DaemonContext:
    """Context passed to RPC handlers.

    Provides access to daemon components without circular imports.
    Uses Any annotations to avoid forward reference issues.

    Attributes:
        daemon: TermtapDaemon - for broadcast_event, state
        queue: ActionQueue - action management
        patterns: PatternStore - pattern matching
        pane_manager: PaneManager - pane state
    """

    daemon: Any
    queue: Any
    patterns: Any
    pane_manager: Any
