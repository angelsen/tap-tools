"""Target ID utilities for multi-target architecture.

PUBLIC API:
  - make_target: Create target string from port and page ID
  - parse_target: Parse target string into port and short ID
  - resolve_target: Match short target to full page info
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


def resolve_target(target: str, pages: list[dict]) -> dict | None:
    """Resolve target to full page info by prefix matching.

    Args:
        target: Target string (e.g., "9222:8c5f3a")
        pages: List of page dicts with 'id' and 'chrome_port' or 'port' fields

    Returns:
        Matching page dict or None if not found

    Examples:
        >>> pages = [{"id": "8C5F3A2B...", "chrome_port": 9222, "title": "GitHub"}]
        >>> resolve_target("9222:8c5f3a", pages)
        {"id": "8C5F3A2B...", "chrome_port": 9222, "title": "GitHub"}
    """
    port, short_id = parse_target(target)
    for page in pages:
        # Support both 'chrome_port' and 'port' keys
        page_port = page.get("chrome_port") or page.get("port")
        if page_port == port:
            if page["id"].lower().startswith(short_id):
                return page
    return None


__all__ = ["make_target", "parse_target", "resolve_target"]
