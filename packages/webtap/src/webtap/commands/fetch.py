"""HTTP fetch request interception and debugging commands."""

from webtap.app import app
from webtap.commands._builders import check_connection, error_response, info_response, table_response
from webtap.commands._tips import get_tips


@app.command(display="markdown", fastmcp={"type": "tool"})
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
    fetch_service = state.service.fetch

    if action == "disable":
        result = fetch_service.disable()
        if "error" in result:
            return error_response(result["error"])
        return info_response(title="Fetch Disabled", fields={"Status": "Interception disabled"})

    elif action == "enable":
        # Check connection first
        if error := check_connection(state):
            return error

        opts = options or {}
        response_stage = opts.get("response", False)

        result = fetch_service.enable(state.cdp, response_stage=response_stage)
        if "error" in result:
            return error_response(result["error"])
        return info_response(
            title="Fetch Enabled",
            fields={
                "Stages": result.get("stages", "Request stage only"),
                "Status": "Requests will pause",
            },
        )

    elif action == "status":
        # Show status
        return info_response(
            title=f"Fetch Status: {'Enabled' if fetch_service.enabled else 'Disabled'}",
            fields={
                "Status": "Enabled" if fetch_service.enabled else "Disabled",
                "Paused": f"{fetch_service.paused_count} requests paused" if fetch_service.enabled else "None",
            },
        )

    else:
        return error_response(f"Unknown action: {action}")


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "application/json"})
def requests(state, limit: int = 50) -> dict:
    """Show paused requests and responses.

    Lists all paused HTTP traffic. Use the ID with inspect() to examine
    details or resume() / fail() to proceed.

    Args:
        limit: Maximum items to show

    Examples:
        requests()           # Show all paused
        inspect(event=47)    # Examine request with rowid 47
        resume(47)           # Continue request 47

    Returns:
        Table of paused requests/responses in markdown
    """
    # Check connection first
    if error := check_connection(state):
        return error

    fetch_service = state.service.fetch

    if not fetch_service.enabled:
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    rows = fetch_service.get_paused_list()

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


@app.command(display="markdown", fastmcp={"type": "tool"})
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
    fetch_service = state.service.fetch

    if not fetch_service.enabled:
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    mods = modifications or {}
    result = fetch_service.continue_request(request, mods, wait_for_next=wait)

    if "error" in result:
        return error_response(result["error"])

    fields = {"Stage": result["stage"], "Continued": f"Row {result['continued']}"}

    # Report follow-up if detected
    if next_event := result.get("next_event"):
        fields["Next Event"] = next_event["description"]
        fields["Next ID"] = str(next_event["rowid"])
        if next_event.get("status"):
            fields["Status"] = next_event["status"]

    if result.get("remaining"):
        fields["Remaining"] = f"{result['remaining']} requests paused"

    return info_response(title="Request Resumed", fields=fields)


@app.command(display="markdown", fastmcp={"type": "tool"})
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
    fetch_service = state.service.fetch

    if not fetch_service.enabled:
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    result = fetch_service.fail_request(request, reason)

    if "error" in result:
        return error_response(result["error"])

    fields = {"Failed": f"Row {result['failed']}", "Reason": result["reason"]}
    if result.get("remaining") is not None:
        fields["Remaining"] = f"{result['remaining']} requests paused"

    return info_response(title="Request Failed", fields=fields)
