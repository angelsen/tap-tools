"""Target ID utilities for multi-target architecture.

PUBLIC API:
  - make_target: Create target string from port and page ID
  - parse_target: Parse target string into port and short ID
"""


def make_target(port: int, page_id: str) -> str:
    """Create target string from port and Chrome page ID.

    Args:
        port: Chrome debug port (e.g., 9222)
        page_id: Chrome page ID (hex string)

    Returns:
        Target string in format "{port}:{6-char-lowercase-hex}"

    Examples:
        >>> make_target(9222, "8C5F3A2B...")
        "9222:8c5f3a"
    """
    return f"{port}:{page_id[:6].lower()}"


def parse_target(target: str) -> tuple[int, str]:
    """Parse target string into port and short ID.

    Args:
        target: Target string in format "{port}:{id}"

    Returns:
        Tuple of (port, short_id)

    Examples:
        >>> parse_target("9222:8c5f3a")
        (9222, "8c5f3a")
    """
    port_str, short_id = target.split(":", 1)
    return int(port_str), short_id


__all__ = ["make_target", "parse_target"]
