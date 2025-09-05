"""Unified error handling for WebTap commands."""

from typing import Optional
from replkit2.textkit import markdown


ERRORS = {
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
    """
    if not (state.cdp and state.cdp.is_connected):
        return error_response("not_connected")
    return None


def error_response(error_key: str, custom_message: str | None = None, **kwargs) -> dict:
    """Build consistent error response in markdown.

    Args:
        error_key: Key from error templates or custom identifier.
        custom_message: Override default message.
        **kwargs: Additional context to add to error response.
    """
    error_info = ERRORS.get(error_key, {})
    message = custom_message or error_info.get("message", "Error occurred")

    builder = markdown().element("alert", message=message, level="error")

    if details := error_info.get("details"):
        builder.text(details)

    if help_items := error_info.get("help"):
        builder.text("**How to fix:**")
        builder.list_(help_items)

    for key, value in kwargs.items():
        if value:
            builder.text(f"_{key}: {value}_")

    return builder.build()


def warning_response(message: str, details: str | None = None) -> dict:
    """Build warning response for non-fatal issues.

    Args:
        message: Warning message text.
        details: Additional details.
    """
    builder = markdown().element("alert", message=message, level="warning")
    if details:
        builder.text(details)
    return builder.build()


def invalid_options_error(message: str, expected: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Create error response for invalid options dict.

    Args:
        message: Error message describing the issue.
        expected: Optional example of expected format.
    """
    builder = markdown().element("alert", message=message, level="error")

    if expected:
        builder.text("**Expected format:**")
        import json

        builder.code_block(json.dumps(expected, indent=2), language="json")

    return builder.build()


def missing_param_error(param: str, command: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Create error response for missing required parameter.

    Args:
        param: Name of the missing parameter.
        command: Optional command name for context.
    """
    message = f"Required parameter '{param}' not provided"
    if command:
        message = f"{command}: {message}"

    builder = markdown().element("alert", message=message, level="error")
    builder.text(f"The '{param}' parameter is required for this operation")

    return builder.build()
