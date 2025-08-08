"""Utility functions for termtap.

PUBLIC API:
  - truncate_command: Format command for display with proper escaping
"""


def truncate_command(command: str, max_length: int = 40) -> str:
    """Truncate and format command for display.

    Handles:
    - Newline escaping (\\n -> \\\\n for display)
    - Length truncation with ellipsis
    - Safe display of multi-line commands

    Args:
        command: The command string to format.
        max_length: Maximum length before truncation. Defaults to 40.

    Returns:
        Formatted command string safe for display.
    """
    formatted = command.replace("\n", "\\n")

    if len(formatted) > max_length:
        return formatted[: max_length - 3] + "..."

    return formatted
