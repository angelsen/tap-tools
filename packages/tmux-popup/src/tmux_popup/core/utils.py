"""Internal utility functions for tmux-popup core functionality."""

from typing import Tuple, Optional, Union


def parse_spacing(spacing: Optional[str]) -> Tuple[int, int, int, int]:
    """Parse spacing string (margin/padding) into top, right, bottom, left values.

    Supports formats:
    - "1" -> all sides = 1
    - "1 2" -> vertical = 1, horizontal = 2
    - "1 2 3" -> top = 1, horizontal = 2, bottom = 3
    - "1 2 3 4" -> top = 1, right = 2, bottom = 3, left = 4

    Args:
        spacing: Spacing string or None

    Returns:
        Tuple of (top, right, bottom, left)
    """
    if not spacing:
        return (0, 0, 0, 0)

    parts = spacing.strip().split()

    if len(parts) == 1:
        # All sides same
        val = int(parts[0])
        return (val, val, val, val)
    elif len(parts) == 2:
        # Vertical, horizontal
        vert = int(parts[0])
        horiz = int(parts[1])
        return (vert, horiz, vert, horiz)
    elif len(parts) == 3:
        # Top, horizontal, bottom
        top = int(parts[0])
        horiz = int(parts[1])
        bottom = int(parts[2])
        return (top, horiz, bottom, horiz)
    elif len(parts) == 4:
        # Top, right, bottom, left
        return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    else:
        raise ValueError(f"Invalid spacing format: {spacing}")


def get_horizontal_spacing(spacing: Optional[str]) -> int:
    """Get total horizontal spacing (left + right) from spacing string.

    Args:
        spacing: Spacing string or None

    Returns:
        Total horizontal spacing
    """
    top, right, bottom, left = parse_spacing(spacing)
    return left + right


def get_vertical_spacing(spacing: Optional[str]) -> int:
    """Get total vertical spacing (top + bottom) from spacing string.

    Args:
        spacing: Spacing string or None

    Returns:
        Total vertical spacing
    """
    top, right, bottom, left = parse_spacing(spacing)
    return top + bottom


def calculate_content_dimensions(
    total_width: Optional[Union[int, str]],
    total_height: Optional[Union[int, str]],
    border: str = "hidden",
    margin: Optional[str] = None,
    padding: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Calculate content dimensions after subtracting border, margin, and padding.

    This centralizes the logic for space self-management.

    Args:
        total_width: Total allocated width (can be runtime variable like "$COL_WIDTH")
        total_height: Total allocated height
        border: Border style ("hidden", "none", or actual border)
        margin: Margin string
        padding: Padding string (handled by gum, but we track for clarity)

    Returns:
        Tuple of (content_width, content_height) as strings for shell script
    """
    content_width = None
    content_height = None

    # Calculate total deductions
    width_deductions = 0
    height_deductions = 0

    # Border takes 2 chars if real
    if border not in ["none", "hidden"]:
        width_deductions += 2
        height_deductions += 2

    # Margin reduces available space
    if margin:
        width_deductions += get_horizontal_spacing(margin)
        height_deductions += get_vertical_spacing(margin)

    # Note: Padding is handled internally by gum, not deducted here

    # Apply deductions
    if total_width is not None:
        width_str = str(total_width)
        if width_deductions > 0:
            if width_str.startswith("$"):
                # Runtime variable
                content_width = f"$(({width_str} - {width_deductions}))"
            elif width_str.isdigit():
                # Fixed value
                content_width = str(max(1, int(width_str) - width_deductions))
            else:
                # Complex expression, wrap it
                content_width = f"$(({width_str} - {width_deductions}))"
        else:
            content_width = width_str

    if total_height is not None:
        height_str = str(total_height)
        if height_deductions > 0:
            if height_str.startswith("$"):
                # Runtime variable
                content_height = f"$(({height_str} - {height_deductions}))"
            elif height_str.isdigit():
                # Fixed value
                content_height = str(max(1, int(height_str) - height_deductions))
            else:
                # Complex expression
                content_height = f"$(({height_str} - {height_deductions}))"
        else:
            content_height = height_str

    return content_width, content_height
