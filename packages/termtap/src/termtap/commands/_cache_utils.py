"""Internal cache utilities for termtap commands."""

from typing import Optional, Tuple, List, Any
from math import ceil


def _paginate_content(content: str, page: int, lines_per_page: int = 50) -> Tuple[str, int]:
    """Paginate content with reverse ordering (page 0 = newest).

    Args:
        content: Full content to paginate.
        page: Page number (0-based, 0 = most recent).
        lines_per_page: Lines per page. Defaults to 50.

    Returns:
        Tuple of (page_content, total_pages).
    """
    lines = content.splitlines()
    total_pages = ceil(len(lines) / lines_per_page) if lines else 1

    end = len(lines) - (page * lines_per_page)
    start = max(0, end - lines_per_page)

    page_content = "\n".join(lines[start:end]) if start < end else ""
    return page_content, total_pages


def _build_frontmatter(
    target: Any,
    lines_shown: int,
    total_lines: int,
    page: int = 1,
    cached: bool = False,
    cache_time: Optional[float] = None,
    lines_per_page: int = 50,
    **extras,
) -> dict:
    """Build unified frontmatter for commands.

    Args:
        target: Target pane(s).
        lines_shown: Number of lines displayed.
        total_lines: Total lines available.
        page: Current page number. Defaults to 1.
        cached: Whether content is cached. Defaults to False.
        cache_time: When content was cached. Defaults to None.
        lines_per_page: Lines per page for total_pages calculation. Defaults to 50.
        **extras: Command-specific fields.

    Returns:
        Consistent frontmatter dict.
    """
    frontmatter = {
        "target": target,
        "pane": target if isinstance(target, str) else target,
        "lines": f"{lines_shown}/{total_lines}",
        "page": page,
        "total_pages": ceil(total_lines / lines_per_page) if total_lines > 0 else 1,
        "cached": cached,
    }

    if cache_time is not None:
        frontmatter["cache_time"] = cache_time

    frontmatter.update(extras)

    return frontmatter


def _format_pane_output(
    outputs: List[Tuple[str, str]],
    page: Optional[int] = None,
    lines_per_page: int = 50,
    cached: bool = False,
    cache_time: Optional[float] = None,
    **extras,
) -> dict:
    """Format output from one or more panes.

    Args:
        outputs: List of (session_window_pane, content) tuples.
        page: Page number if paginating. Defaults to None.
        lines_per_page: Lines per page. Defaults to 50.
        cached: Whether content is from cache. Defaults to False.
        cache_time: When content was cached. Defaults to None.
        **extras: Additional frontmatter fields.

    Returns:
        Formatted response with elements and frontmatter.
    """
    elements = []
    total_lines = 0
    shown_lines = 0

    for swp, content in outputs:
        lines = content.splitlines()
        total_lines += len(lines)

        if page is not None:
            actual_page = page
            if page < 0:
                content_pages = ceil(len(lines) / lines_per_page) if lines else 1
                actual_page = content_pages + page
                if actual_page < 0:
                    actual_page = 0
            elif page > 0:
                # Pages > 0 are 1-based
                actual_page = page - 1

            page_content, total_pages = _paginate_content(content, actual_page, lines_per_page)

            # Add read more hint if there are more pages
            if actual_page + 1 < total_pages:
                display_page = page if page > 0 else 1
                next_page = display_page + 1
                hint = f'... read more with readMcpResource("termtap://pane/{swp}/{next_page}", "termtap")\n'
                page_content = hint + page_content if page_content else hint
        else:
            # Fresh read - still check if truncated
            page_content = "\n".join(lines[-lines_per_page:]) if lines else ""
            total_pages = ceil(len(lines) / lines_per_page) if lines else 1
            if total_pages > 1:
                hint = f'... read more with readMcpResource("termtap://pane/{swp}/2", "termtap")\n'
                page_content = hint + page_content if page_content else hint

        shown_lines += len(page_content.splitlines())

        if len(outputs) > 1:
            elements.append({"type": "heading", "content": swp, "level": 3})

        elements.append(
            {
                "type": "code_block",
                "content": page_content or "[No output]",
                "language": "text",
            }
        )

    panes = [swp for swp, _ in outputs]
    target = panes[0] if len(panes) == 1 else panes

    # Always show 1-based pages to users
    display_page = page if page and page > 0 else 1

    return {
        "elements": elements,
        "frontmatter": _build_frontmatter(
            target=target,
            lines_shown=shown_lines,
            total_lines=total_lines,
            page=display_page,
            cached=cached,
            cache_time=cache_time,
            lines_per_page=lines_per_page,
            **extras,
        ),
    }


def _truncate_command(command: str, max_length: int = 50) -> str:
    """Truncate long commands for display in frontmatter.

    Always uses first line of command for consistency.

    Args:
        command: Command string to truncate.
        max_length: Maximum length. Defaults to 50.

    Returns:
        Truncated command with ellipsis if needed.
    """
    lines = command.splitlines()
    first_line = lines[0] if lines else command

    if len(first_line) <= max_length:
        return first_line
    return first_line[: max_length - 3] + "..."
