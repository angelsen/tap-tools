"""Error handling utilities for termtap commands.

Provides consistent error formatting and response generation across all commands.

PUBLIC API:
  - markdown_error_response: Create error response for markdown display
  - table_error_response: Create error response for table display
  - string_error_response: Create error response for string display
"""

from typing import Any


def markdown_error_response(message: str) -> dict[str, Any]:
    """Create error response for markdown display commands.

    Args:
        message: The error message to display

    Returns:
        Markdown display dict with error element
    """
    return {"elements": [{"type": "text", "content": f"Error: {message}"}], "frontmatter": {"status": "error"}}


def table_error_response(message: str) -> list[dict[str, Any]]:
    """Create error response for table display commands.

    Args:
        message: The error message (will be logged)

    Returns:
        Empty list (tables show nothing on error)
    """
    from logging import getLogger

    logger = getLogger(__name__)
    logger.warning(f"Command failed: {message}")
    return []


def string_error_response(message: str) -> str:
    """Create error response for string display commands.

    Args:
        message: The error message to display

    Returns:
        Formatted error string
    """
    return f"Error: {message}"
