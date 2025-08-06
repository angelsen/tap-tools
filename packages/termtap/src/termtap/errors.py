"""Shared error handling utilities for termtap commands.

This module provides consistent error formatting and response generation
across all commands, following the ERROR_HANDLING_SPEC.md guidelines.

Commands should handle their own business logic (like service suggestions)
before using these generic error utilities.

PUBLIC API:
  - markdown_error_response: Create error response for markdown display
  - table_error_response: Create error response for table display
  - string_error_response: Create error response for string display
  - RuntimeError: Re-exported standard exception for consistency
"""

from typing import Any

# Re-export for consistency with PUBLIC API
RuntimeError = RuntimeError


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
    # Import logger locally to avoid circular imports
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
