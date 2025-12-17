"""Pydantic request models for API endpoints.

PUBLIC API:
  - ConnectRequest: Chrome page connection parameters
  - FetchRequest: Fetch interception configuration
  - CDPRequest: CDP command relay parameters
  - ResumeRequest: Resume paused request parameters
  - FailRequest: Fail paused request parameters
  - FulfillRequest: Fulfill paused request with custom response
"""

from typing import Any, Dict

from pydantic import BaseModel


class ConnectRequest(BaseModel):
    """Request model for connecting to a Chrome page.

    Supports either page index (for REPL/MCP) or page_id (for extension).
    """

    page: int | None = None  # Page index (0-based)
    page_id: str | None = None  # Page ID from Chrome


class FetchRequest(BaseModel):
    """Request model for enabling/disabling fetch interception."""

    enabled: bool
    response_stage: bool = False


class CDPRequest(BaseModel):
    """Request model for CDP command relay."""

    method: str
    params: Dict[str, Any] = {}


class ResumeRequest(BaseModel):
    """Request model for resuming a paused request."""

    rowid: int
    modifications: Dict[str, Any] = {}
    wait: float = 0.5


class FailRequest(BaseModel):
    """Request model for failing a paused request."""

    rowid: int
    reason: str = "BlockedByClient"


class FulfillRequest(BaseModel):
    """Request model for fulfilling a paused request with custom response."""

    rowid: int
    response_code: int = 200
    response_headers: list[dict[str, str]] = []
    body: str = ""


class ClearRequest(BaseModel):
    """Request model for clearing data stores."""

    events: bool = True
    console: bool = False
