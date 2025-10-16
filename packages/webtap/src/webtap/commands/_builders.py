"""Response builders using ReplKit2 v0.10.0+ markdown elements.

USAGE GUIDELINES:

Use builders for:
  ✅ Simple responses (error, info, success, warning)
  ✅ Tables with standard format
  ✅ Code execution results
  ✅ Repeated patterns across commands

Use manual building for:
  ❌ Complex multi-section layouts (>20 lines)
  ❌ Conditional sections with deep nesting
  ❌ Custom workflows (wizards, dashboards)
  ❌ Dual-mode resource views with tutorials

Examples:
  - network() - Simple table → Use table_response()
  - javascript() - Code result → Use code_result_response()
  - server() - Custom dashboard → Manual OK
  - selections() resource mode - Tutorial layout → Manual OK

Available builders:
  - table_response() - Tables with headers, warnings, tips
  - info_response() - Key-value pairs with optional heading and tips
  - error_response() - Errors with suggestions
  - success_response() - Success messages with details
  - warning_response() - Warnings with suggestions
  - check_connection() - Helper for CDP connection validation
  - check_fetch_enabled() - Helper for fetch interception validation
  - code_result_response() - Code execution with result display
  - code_response() - Simple code block display
"""

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
    tips: list[str] | None = None,
) -> dict:
    """Build info display with key-value pairs.

    Args:
        title: Optional info title
        fields: Dict of field names to values
        extra: Optional extra content (raw markdown)
        tips: Optional developer tips/guidance
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

    if tips:
        elements.append({"type": "heading", "content": "Next Steps", "level": 3})
        elements.append({"type": "list", "items": tips})

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


# Connection helpers


def check_connection(state):
    """Check CDP connection, return error response if not connected.

    Returns error_response() if not connected, None otherwise.
    Use pattern: `if error := check_connection(state): return error`

    Args:
        state: Application state containing CDP session.

    Returns:
        Error response dict if not connected, None if connected.
    """
    if not (state.cdp and state.cdp.is_connected):
        return error_response(
            "Not connected to Chrome",
            suggestions=[
                "Run `pages()` to see available tabs",
                "Use `connect(0)` to connect to first tab",
                "Or `connect(page_id='...')` for specific tab",
            ],
        )
    return None


def check_fetch_enabled(state):
    """Check fetch interception, return error response if not enabled.

    Args:
        state: Application state containing fetch service.

    Returns:
        Error response dict if not enabled, None if enabled.
    """
    if not state.service.fetch.enabled:
        return error_response(
            "Fetch interception not enabled", suggestions=["Enable with `fetch('enable')` to pause requests"]
        )
    return None


# Code result builders


def code_result_response(
    title: str,
    code: str,
    language: str,
    result: Any = None,
) -> dict:
    """Build code execution result display.

    Args:
        title: Result heading (e.g. "JavaScript Result")
        code: Source code executed
        language: Syntax highlighting language
        result: Execution result (supports dict/list/str/None)

    Returns:
        Markdown response with code and result
    """
    import json

    elements = [
        {"type": "heading", "content": title, "level": 2},
        {"type": "code_block", "content": code, "language": language},
    ]

    if result is not None:
        if isinstance(result, (dict, list)):
            elements.append({"type": "code_block", "content": json.dumps(result, indent=2), "language": "json"})
        else:
            elements.append({"type": "text", "content": f"**Result:** `{result}`"})
    else:
        elements.append({"type": "text", "content": "**Result:** _(no return value)_"})

    return {"elements": elements}


def code_response(
    content: str,
    language: str = "",
    title: str | None = None,
) -> dict:
    """Build simple code block response.

    Args:
        content: Code content to display
        language: Syntax highlighting language
        title: Optional heading above code block

    Returns:
        Markdown response with code block
    """
    elements = []

    if title:
        elements.append({"type": "heading", "content": title, "level": 2})

    elements.append({"type": "code_block", "content": content, "language": language})

    return {"elements": elements}
