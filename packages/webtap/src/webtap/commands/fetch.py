"""HTTP fetch request interception and debugging commands."""

from webtap.app import app
from webtap.commands._builders import check_connection, error_response, info_response, table_response
from webtap.commands._tips import get_mcp_description, get_tips

_fetch_desc = get_mcp_description("fetch")
_resume_desc = get_mcp_description("resume")
_fail_desc = get_mcp_description("fail")


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fetch_desc or ""}
)
def fetch(state, action: str, options: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Control fetch interception.

    When enabled, requests pause for inspection.
    Use requests() to see paused items, resume() or fail() to proceed.

    Args:
        action: Action to perform
            - "enable" - Enable interception
            - "disable" - Disable interception
            - "status" - Get current status
        options: Action-specific options
            - For enable: {"response": true} - Also intercept responses

    Examples:
        fetch("status")                           # Check status
        fetch("enable")                           # Enable request stage
        fetch("enable", {"response": true})       # Both stages
        fetch("disable")                          # Disable

    Returns:
        Fetch interception status
    """
    if action == "disable":
        result = state.client.fetch("disable")
        if "error" in result:
            return error_response(result["error"])
        return info_response(title="Fetch Disabled", fields={"Status": "Interception disabled"})

    elif action == "enable":
        # Check connection first
        if error := check_connection(state):
            return error

        result = state.client.fetch("enable", options)
        if "error" in result:
            return error_response(result["error"])

        # Extract stages info from result
        stages = "Request and Response stages" if result.get("response_stage") else "Request stage only"
        return info_response(
            title="Fetch Enabled",
            fields={
                "Stages": stages,
                "Status": "Requests will pause",
            },
        )

    elif action == "status":
        # Get status from daemon
        status = state.client.status()
        if status.get("error"):
            return error_response(status["error"])

        fetch_state = status.get("fetch", {})
        fetch_enabled = fetch_state.get("enabled", False)
        paused_count = fetch_state.get("paused_count", 0) if fetch_enabled else 0

        return info_response(
            title=f"Fetch Status: {'Enabled' if fetch_enabled else 'Disabled'}",
            fields={
                "Status": "Enabled" if fetch_enabled else "Disabled",
                "Paused": f"{paused_count} requests paused" if fetch_enabled else "None",
            },
        )

    else:
        return error_response(f"Unknown action: {action}")


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "text/markdown"})
def requests(state, limit: int = 50) -> dict:
    """Show paused requests and responses.

    Lists all paused HTTP traffic. Use the ID with request() to examine
    details or resume() / fail() to proceed.

    Args:
        limit: Maximum items to show

    Examples:
        requests()           # Show all paused
        request(47)          # View request details
        resume(47)           # Continue request 47

    Returns:
        Table of paused requests/responses in markdown
    """
    # Check connection first
    if error := check_connection(state):
        return error

    # Get status to check if fetch is enabled
    status = state.client.status()
    if status.get("error"):
        return error_response(status["error"])

    if not status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Get paused requests from daemon
    rows = state.client.paused_requests()

    # Apply limit
    if limit and len(rows) > limit:
        rows = rows[:limit]

    # Build warnings if needed
    warnings = []
    if limit and len(rows) == limit:
        warnings.append(f"Showing first {limit} paused requests (use limit parameter to see more)")

    # Get tips from TIPS.md
    tips = None
    if rows:
        example_id = rows[0]["ID"]
        tips = get_tips("requests", context={"id": example_id})

    # Build markdown response
    return table_response(
        title="Paused Requests",
        headers=["ID", "Stage", "Method", "Status", "URL"],
        rows=rows,
        summary=f"{len(rows)} requests paused",
        warnings=warnings,
        tips=tips,
    )


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _resume_desc or ""}
)
def resume(state, request: int, wait: float = 0.5, modifications: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Resume a paused request.

    For Request stage, can modify:
        url, method, headers, postData

    For Response stage, can modify:
        responseCode, responseHeaders

    Args:
        request: Request row ID from requests() table
        wait: Wait time for next event in seconds (default: 0.5)
        modifications: Request/response modifications dict
            - {"url": "..."} - Change URL
            - {"method": "POST"} - Change method
            - {"headers": [{"name": "X-Custom", "value": "test"}]} - Set headers
            - {"responseCode": 404} - Change response code
            - {"responseHeaders": [...]} - Modify response headers

    Examples:
        resume(123)                               # Simple resume
        resume(123, wait=1.0)                    # Wait for redirect
        resume(123, modifications={"url": "..."})  # Change URL
        resume(123, modifications={"method": "POST"})  # Change method
        resume(123, modifications={"headers": [{"name":"X-Custom","value":"test"}]})

    Returns:
        Continuation status with any follow-up events detected
    """
    # Get status to check if fetch is enabled
    status = state.client.status()
    if status.get("error"):
        return error_response(status["error"])

    if not status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Resume via daemon
    response = state.client.resume_request(request, modifications or {}, wait)

    if "error" in response:
        return error_response(response["error"])

    result = response.get("result", {})
    fields = {"Stage": result.get("stage", "unknown"), "Continued": f"Row {result.get('continued', request)}"}

    # Report follow-up if detected
    if next_event := result.get("next_event"):
        fields["Next Event"] = next_event["description"]
        fields["Next ID"] = str(next_event["rowid"])
        if next_event.get("status"):
            fields["Status"] = next_event["status"]

    if result.get("remaining"):
        fields["Remaining"] = f"{result['remaining']} requests paused"

    return info_response(title="Request Resumed", fields=fields)


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fail_desc or ""}
)
def fail(state, request: int, reason: str = "BlockedByClient") -> dict:
    """Fail a paused request.

    Args:
        request: Row ID from requests() table
        reason: CDP error reason (default: BlockedByClient)
                Options: Failed, Aborted, TimedOut, AccessDenied,
                        ConnectionClosed, ConnectionReset, ConnectionRefused,
                        ConnectionAborted, ConnectionFailed, NameNotResolved,
                        InternetDisconnected, AddressUnreachable, BlockedByClient,
                        BlockedByResponse

    Examples:
        fail(47)                          # Fail specific request
        fail(47, reason="AccessDenied")  # Fail with specific reason

    Returns:
        Failure status
    """
    # Get status to check if fetch is enabled
    status = state.client.status()
    if status.get("error"):
        return error_response(status["error"])

    if not status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Fail via daemon
    response = state.client.fail_request(request, reason)

    if "error" in response:
        return error_response(response["error"])

    result = response.get("result", {})
    fields = {"Failed": f"Row {result.get('failed', request)}", "Reason": result.get("reason", reason)}
    if result.get("remaining") is not None:
        fields["Remaining"] = f"{result['remaining']} requests paused"

    return info_response(title="Request Failed", fields=fields)
