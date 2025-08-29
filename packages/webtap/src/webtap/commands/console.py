"""Console monitoring commands."""

from webtap.app import app
from webtap.commands._utils import truncate_string




@app.command(display="table", headers=["Level", "Source", "Message", "Time"])
def console(state, limit: int = 50):
    """
    Show console messages in table format.
    
    Args:
        limit: Max results (default: 50)
    
    Examples:
        console()           # Recent console messages
        console(limit=100)  # Show more messages
    
    Returns:
        Table of console messages
    """
    if not state.cdp or not state.cdp.is_connected:
        return []
    
    # Table view - extract specific fields (handling both event types)
    sql = f"""
    SELECT 
        COALESCE(
            json_extract_string(event, '$.params.type'),
            json_extract_string(event, '$.params.entry.level')
        ) as Level,
        COALESCE(
            json_extract_string(event, '$.params.source'),
            json_extract_string(event, '$.params.entry.source'),
            'console'
        ) as Source,
        COALESCE(
            json_extract_string(event, '$.params.args[0].value'),
            json_extract_string(event, '$.params.entry.text')
        ) as Message,
        COALESCE(
            json_extract_string(event, '$.params.timestamp'),
            json_extract_string(event, '$.params.entry.timestamp')
        ) as Time
    FROM events 
    WHERE json_extract_string(event, '$.method') IN ('Runtime.consoleAPICalled', 'Log.entryAdded')
    ORDER BY rowid DESC LIMIT {limit}
    """
    
    results = state.cdp.query(sql)
    
    # Format for table display
    rows = []
    for row in results:
        level, source, message, timestamp = row
        rows.append({
            "Level": (level or "log").upper(),
            "Source": source or "console",
            "Message": truncate_string(message, 80),
            "Time": timestamp[:19] if timestamp else "-"  # Just date and time
        })
    
    return rows




@app.command()
def clear_console(state):
    """Clear console events from browser.
    
    Returns:
        Clear status message
    """
    if not state.cdp or not state.cdp.is_connected:
        return "Not connected"
    
    # Clear browser console
    try:
        state.cdp.execute("Runtime.discardConsoleEntries")
        return "Console cleared"
    except Exception as e:
        return f"Failed to clear console: {e}"