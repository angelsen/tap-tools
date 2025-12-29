"""WebTap service layer for managing CDP state and operations.

Provides a clean interface between REPL commands/API endpoints and the underlying
CDP session. Services encapsulate domain-specific queries and operations, making
them reusable across different interfaces.

PUBLIC API:
  - WebTapService: Main service orchestrating all domain services
  - SetupService: Service for installing WebTap components
  - ConnectionManager: Thread-safe connection lifecycle management
  - ActiveConnection: Tracks an active CDP connection
  - TargetState: Per-target connection state enum
  - StateSnapshot: Immutable state for thread-safe SSE broadcasting
"""

from webtap.services.connection import ActiveConnection, ConnectionManager, TargetState
from webtap.services.main import WebTapService
from webtap.services.setup import SetupService
from webtap.services.state_snapshot import StateSnapshot

__all__ = [
    "WebTapService",
    "SetupService",
    "ConnectionManager",
    "ActiveConnection",
    "TargetState",
    "StateSnapshot",
]
