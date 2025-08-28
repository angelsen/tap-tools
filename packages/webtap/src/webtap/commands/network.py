"""Network monitoring commands."""

from webtap.app import app
from webtap.cdp.helpers import build_network_row, format_size, truncate_url


@app.command(display="table", headers=["ID", "Method", "Status", "URL", "Type", "Size"])
def network(state, id: str | None = None, body: bool = False, limit: int = 20):
    """Show network requests.

    Args:
        id: Request ID for detail view (returns raw)
        body: Include response body in detail view
        limit: Max number of requests to show in table

    Returns:
        Table of requests or raw detail for single request
    """
    if not state.cdp.connected.is_set():
        return []

    # Build rows from all network events
    rows = []
    for request_id, events in state.cdp.network_events.items():
        row = build_network_row(request_id, events)
        rows.append(row)

    # Single item detail - return raw
    if id:
        for row in rows:
            if row["id"] == id or row["id"].startswith(id):  # Allow partial ID match
                result = {
                    "id": row["id"],
                    "url": row["url"],
                    "method": row["method"],
                    "status": row["status"],
                    "type": row["type"],
                    "size": row["size"],
                    "events": len(row["_events"]),
                }

                # Add body if requested
                if body and row["status"]:
                    try:
                        body_response = state.cdp.execute("Network.getResponseBody", {"requestId": row["id"]})
                        result["body"] = body_response.get("body")
                        result["base64Encoded"] = body_response.get("base64Encoded", False)
                    except Exception as e:
                        result["body_error"] = str(e)

                # Add raw events
                result["_events"] = row["_events"]

                # Override display to raw for detail view
                network.__display__ = None  # pyright: ignore[reportFunctionMemberAccess]
                return result

        network.__display__ = None  # pyright: ignore[reportFunctionMemberAccess]
        return {"error": f"Request {id} not found"}

    # Table view - newest first
    rows.reverse()

    # Format for table display
    table_rows = []
    for row in rows[:limit]:
        table_rows.append(
            {
                "ID": row["id"][:8] + "..." if len(row["id"]) > 11 else row["id"],
                "Method": row["method"],
                "Status": str(row["status"]) if row["status"] else "-",
                "URL": truncate_url(row["url"], 50),
                "Type": row["type"] or "-",
                "Size": format_size(row["size"]) if row["size"] else "-",
            }
        )

    return table_rows
