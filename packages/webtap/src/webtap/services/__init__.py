"""WebTap service layer for managing CDP state and operations.

The service layer provides a clean interface between REPL commands/API endpoints
and the underlying CDP session. Services encapsulate domain-specific queries and
operations, making them reusable across different interfaces.

PUBLIC API:
  - WebTapService: Main service orchestrating all domain services
  - SetupService: Service for installing WebTap components
"""

from webtap.services.main import WebTapService
from webtap.services.setup import SetupService

__all__ = ["WebTapService", "SetupService"]
