"""Composable output filter functions for termtap handlers.

Filters transform process output before display, cleaning up verbose output
and improving readability.

PUBLIC API:
  - strip_trailing_empty_lines: Remove trailing empty lines from output
  - collapse_empty_lines: Collapse consecutive empty lines above threshold
"""


def strip_trailing_empty_lines(content: str) -> str:
    """Strip trailing empty lines that tmux adds to fill pane height.

    Preserves empty lines within the content but removes padding at the end.

    Args:
        content: The text content to filter.

    Returns:
        Content with trailing empty lines removed.
    """
    if not content:
        return ""

    lines = content.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def collapse_empty_lines(content: str, threshold: int = 5) -> str:
    """Collapse consecutive empty lines above threshold.

    Args:
        content: The text content to filter.
        threshold: Number of consecutive empty lines before collapsing.

    Returns:
        Content with collapsed empty lines.
    """
    if not content:
        return content

    lines = content.splitlines()
    if not lines:
        return content

    result = []
    empty_count = 0

    for line in lines:
        if not line.strip():
            empty_count += 1
        else:
            if empty_count > 0:
                if empty_count > threshold:
                    result.append("")
                    omitted = empty_count - 2
                    if omitted > 0:
                        result.append(f"... {omitted} empty lines omitted ...")
                    result.append("")
                else:
                    result.extend([""] * empty_count)
                empty_count = 0

            result.append(line)

    if empty_count > 0:
        if empty_count > threshold:
            result.append("")
            omitted = empty_count - 1
            if omitted > 0:
                result.append(f"... {omitted} empty lines omitted ...")
        else:
            result.extend([""] * empty_count)

    if content.endswith("\n"):
        return "\n".join(result) + "\n"
    else:
        return "\n".join(result)
