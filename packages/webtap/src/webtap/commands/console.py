"""Browser console message monitoring and display commands."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import table_response, error_response, format_timestamp
from webtap.commands._tips import get_tips

# Truncation values for REPL mode (compact display)
_REPL_TRUNCATE = {
    "Message": {"max": 80, "mode": "end"},
}

# Truncation values for MCP mode (generous for LLM context)
_MCP_TRUNCATE = {
    "Message": {"max": 300, "mode": "end"},
}


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/markdown"},
)
def console(state, limit: int = 50, _ctx: ExecutionContext = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Show console messages with full data.

    Args:
        limit: Max results (default: 50)

    Examples:
        console()           # Recent console messages
        console(limit=100)  # Show more messages

    Returns:
        Table of console messages with full data
    """
    # Get console messages via RPC
    try:
        result = state.client.call("console", limit=limit)
        messages = result.get("messages", [])
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    # Mode-specific configuration
    is_repl = _ctx and _ctx.is_repl()

    # Build rows with mode-specific formatting
    rows = [
        {
            "ID": str(m.get("id", i)),
            "Level": m.get("level", "unknown"),
            "Source": m.get("source", ""),
            "Message": m.get("message", ""),
            # REPL: human-friendly time, MCP: raw timestamp for LLM
            "Time": format_timestamp(m.get("timestamp")) if is_repl else (m.get("timestamp") or 0),
        }
        for i, m in enumerate(messages)
    ]

    # Build response
    warnings = []
    if limit and len(messages) == limit:
        warnings.append(f"Showing first {limit} messages (use limit parameter to see more)")

    # Get contextual tips from TIPS.md
    tips = None
    if rows:
        # Focus on error/warning messages for debugging
        error_rows = [r for r in rows if r.get("Level", "").upper() in ["ERROR", "WARN", "WARNING"]]
        example_id = error_rows[0]["ID"] if error_rows else rows[0]["ID"]
        tips = get_tips("console", context={"id": example_id})

    # Use mode-specific truncation
    truncate = _REPL_TRUNCATE if is_repl else _MCP_TRUNCATE

    return table_response(
        title="Console Messages",
        headers=["ID", "Level", "Source", "Message", "Time"],
        rows=rows,
        summary=f"{len(rows)} messages",
        warnings=warnings,
        tips=tips,
        truncate=truncate,
    )
