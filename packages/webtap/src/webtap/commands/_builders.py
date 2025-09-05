"""Response builders using ReplKit2 v0.10.0+ markdown elements."""

from typing import Any


def table_response(
    title: str | None = None,
    headers: list[str] | None = None,
    rows: list[dict] | None = None,
    summary: str | None = None,
    warnings: list[str] | None = None,
    tips: list[str] | None = None,
) -> dict:
    """Build table response with full data.

    Args:
        title: Optional table title
        headers: Column headers
        rows: Data rows with FULL data
        summary: Optional summary text
        warnings: Optional warning messages
        tips: Optional developer tips/guidance
    """
    elements = []

    if title:
        elements.append({"type": "heading", "content": title, "level": 2})

    if warnings:
        for warning in warnings:
            elements.append({"type": "alert", "message": warning, "level": "warning"})

    if headers and rows:
        elements.append({"type": "table", "headers": headers, "rows": rows})
    elif rows:  # Headers can be inferred from row keys
        elements.append({"type": "table", "rows": rows})
    else:
        elements.append({"type": "text", "content": "_No data available_"})

    if summary:
        elements.append({"type": "text", "content": f"_{summary}_"})

    if tips:
        elements.append({"type": "heading", "content": "Next Steps", "level": 3})
        elements.append({"type": "list", "items": tips})

    return {"elements": elements}


def info_response(
    title: str | None = None,
    fields: dict | None = None,
    extra: str | None = None,
) -> dict:
    """Build info display with key-value pairs.

    Args:
        title: Optional info title
        fields: Dict of field names to values
        extra: Optional extra content (raw markdown)
    """
    elements = []

    if title:
        elements.append({"type": "heading", "content": title, "level": 2})

    if fields:
        for key, value in fields.items():
            if value is not None:
                elements.append({"type": "text", "content": f"**{key}:** {value}"})

    if extra:
        elements.append({"type": "raw", "content": extra})

    if not elements:
        elements.append({"type": "text", "content": "_No information available_"})

    return {"elements": elements}


def error_response(message: str, suggestions: list[str] | None = None) -> dict:
    """Build error response with optional suggestions.

    Args:
        message: Error message
        suggestions: Optional list of suggestions
    """
    elements: list[dict[str, Any]] = [{"type": "alert", "message": message, "level": "error"}]

    if suggestions:
        elements.append({"type": "text", "content": "**Try:**"})
        elements.append({"type": "list", "items": suggestions})

    return {"elements": elements}


def success_response(message: str, details: dict | None = None) -> dict:
    """Build success response with optional details.

    Args:
        message: Success message
        details: Optional dict of additional details
    """
    elements = [{"type": "alert", "message": message, "level": "success"}]

    if details:
        for key, value in details.items():
            if value is not None:
                elements.append({"type": "text", "content": f"**{key}:** {value}"})

    return {"elements": elements}


def warning_response(message: str, suggestions: list[str] | None = None) -> dict:
    """Build warning response with optional suggestions.

    Args:
        message: Warning message
        suggestions: Optional list of suggestions
    """
    elements: list[dict[str, Any]] = [{"type": "alert", "message": message, "level": "warning"}]

    if suggestions:
        elements.append({"type": "text", "content": "**Try:**"})
        elements.append({"type": "list", "items": suggestions})

    return {"elements": elements}
