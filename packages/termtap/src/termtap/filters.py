"""Output filter functions for termtap.

These are composable filters that handlers can use to transform output.
"""


def collapse_empty_lines(content: str, threshold: int = 5) -> str:
    """Collapse consecutive empty lines above threshold.

    Args:
        content: The text content to filter
        threshold: Number of consecutive empty lines before collapsing

    Returns:
        Content with collapsed empty lines
    """
    if not content:
        return content

    lines = content.splitlines()
    if not lines:
        return content

    result = []
    empty_count = 0

    for line in lines:
        if not line.strip():  # Empty line
            empty_count += 1
        else:
            # Handle accumulated empty lines
            if empty_count > 0:
                if empty_count > threshold:
                    # Collapse: keep one empty line, add message, keep one more
                    result.append("")  # One empty line before
                    omitted = empty_count - 2  # We're keeping 2
                    if omitted > 0:
                        result.append(f"... {omitted} empty lines omitted ...")
                    result.append("")  # One empty line after
                else:
                    # Keep all empty lines if below threshold
                    result.extend([""] * empty_count)
                empty_count = 0

            # Add the non-empty line
            result.append(line)

    # Handle trailing empty lines
    if empty_count > 0:
        if empty_count > threshold:
            result.append("")  # One empty line
            omitted = empty_count - 1
            if omitted > 0:
                result.append(f"... {omitted} empty lines omitted ...")
        else:
            result.extend([""] * empty_count)

    # Preserve the original ending (newline or not)
    if content.endswith("\n"):
        return "\n".join(result) + "\n"
    else:
        return "\n".join(result)
