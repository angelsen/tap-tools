"""Unified error handling for WebTap commands.

Provides consistent error response formatting and connection validation
for all WebTap command modules.

PUBLIC API:
  - check_connection: Validate CDP connection state
  - error_response: Build formatted error responses
  - warning_response: Build formatted warning responses
"""

from typing import Optional
from replkit2.textkit import markdown


# Standard error message templates
_ERRORS = {
    "not_connected": {
        "message": "Not connected to Chrome",
        "details": "Use `connect()` to connect to a page",
        "help": [
            "Run `pages()` to see available tabs",
            "Use `connect(0)` to connect to first tab",
            "Or `connect(page_id='...')` for specific tab",
        ],
    },
    "fetch_disabled": {
        "message": "Fetch interception not enabled",
        "details": "Enable with `fetch(enable=True)` to pause requests",
    },
    "no_data": {"message": "No data available", "details": "The requested data is not available"},
}


def check_connection(state) -> Optional[dict]:
    """Check CDP connection and return error response if not connected.

    Args:
        state: Application state containing CDP session.

    Returns:
        Error dict if not connected, None if connected.
    """
    if not (state.cdp and state.cdp.is_connected):
        return error_response("not_connected")
    return None


def error_response(error_key: str, custom_message: str | None = None, **kwargs) -> dict:
    """Build consistent error response in markdown.

    Args:
        error_key: Key from error templates or custom identifier.
        custom_message: Override default message. Defaults to None.
        **kwargs: Additional context to add to error response.

    Returns:
        Markdown dict with error formatting.
    """
    error_info = _ERRORS.get(error_key, {})
    message = custom_message or error_info.get("message", "Error occurred")

    builder = markdown().element("alert", message=message, level="error")

    # Add details if available
    if details := error_info.get("details"):
        builder.text(details)

    # Add help items if available
    if help_items := error_info.get("help"):
        builder.text("**How to fix:**")
        builder.list(help_items)

    # Add any custom context
    for key, value in kwargs.items():
        if value:
            builder.text(f"_{key}: {value}_")

    return builder.build()


def warning_response(message: str, details: str | None = None) -> dict:
    """Build warning response for non-fatal issues.

    Args:
        message: Warning message text.
        details: Additional details. Defaults to None.

    Returns:
        Markdown dict with warning formatting.
    """
    builder = markdown().element("alert", message=message, level="warning")
    if details:
        builder.text(details)
    return builder.build()
