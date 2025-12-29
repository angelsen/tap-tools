"""HTTP fetch request interception and debugging commands."""

from webtap.app import app
from webtap.commands._builders import error_response, info_response, rpc_call
from webtap.commands._tips import get_mcp_description, get_tips

_fetch_desc = get_mcp_description("fetch")
_resume_desc = get_mcp_description("resume")
_fail_desc = get_mcp_description("fail")
_fulfill_desc = get_mcp_description("fulfill")


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fetch_desc or ""},
)
def fetch(state, action: str, response: bool = False) -> dict:
    """Control fetch interception.

    When enabled, requests pause for inspection.
    Use requests() to see paused items, resume() or fail() to proceed.

    Args:
        action: Action to perform
            - "enable" - Enable interception
            - "disable" - Disable interception
            - "status" - Get current status
        response: Also intercept at Response stage (allows body access before resume)

    Examples:
        fetch("status")                    # Check status
        fetch("enable")                    # Enable request stage only
        fetch("enable", response=True)     # Both stages (can get body)
        fetch("disable")                   # Disable

    Returns:
        Fetch interception status
    """
    if action == "disable":
        _, error = rpc_call(state, "fetch.disable")
        if error:
            return error
        return info_response(title="Fetch Disabled", fields={"Status": "Interception disabled"})

    elif action == "enable":
        result, error = rpc_call(state, "fetch.enable", request=True, response=response)
        if error:
            return error

        stages = "Request and Response stages" if result.get("response_stage") else "Request stage only"
        return info_response(
            title="Fetch Enabled",
            fields={
                "Stages": stages,
                "Status": "Requests will pause",
            },
        )

    elif action == "status":
        status, error = rpc_call(state, "status")
        if error:
            return error

        fetch_state = status.get("fetch", {})
        fetch_enabled = fetch_state.get("enabled", False)
        paused_count = fetch_state.get("paused_count", 0) if fetch_enabled else 0
        capture_enabled = fetch_state.get("capture_enabled", False)

        return info_response(
            title=f"Fetch Status: {'Enabled' if fetch_enabled else 'Disabled'}",
            fields={
                "Intercept": "Enabled" if fetch_enabled else "Disabled",
                "Paused": f"{paused_count} requests" if fetch_enabled else "None",
                "Capture": "Enabled" if capture_enabled else "Disabled",
            },
        )

    else:
        return error_response(f"Unknown action: {action}")


@app.command(display="markdown", fastmcp={"type": "resource", "mime_type": "text/markdown"})
def requests(state, limit: int = 50) -> dict:
    """Show paused requests. Equivalent to network(req_state="paused").

    Args:
        limit: Maximum items to show

    Examples:
        requests()           # Show all paused
        request(583)         # View request details
        resume(583)          # Continue request

    Returns:
        Table of paused requests/responses in markdown
    """
    # Get status to check if fetch is enabled
    status, error = rpc_call(state, "status")
    if error:
        return error
    if not status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Use RPC to get paused network requests
    result, error = rpc_call(state, "network", **{"state": "paused", "limit": limit, "show_all": True})
    if error:
        return error
    requests_data = result.get("requests", [])

    # Check if any request has pause_stage
    has_pause = any(r.get("pause_stage") for r in requests_data)

    # Build rows for table
    rows = []
    for r in requests_data:
        row = {
            "ID": str(r["id"]),
            "Method": r["method"],
            "Status": str(r["status"]) if r["status"] else "-",
            "URL": r["url"],
            "State": r.get("state", "-"),
        }
        if has_pause:
            row["Pause"] = r.get("pause_stage") or "-"
        rows.append(row)

    # Build headers
    headers = ["ID", "Method", "Status", "URL", "State"]
    if has_pause:
        headers.append("Pause")

    # Build tips
    tips = []
    if rows:
        example_id = rows[0]["ID"]
        context_tips = get_tips("requests", context={"id": example_id})
        if context_tips:
            tips.extend(context_tips)

    from webtap.commands._builders import table_response

    return table_response(
        title="Paused Requests",
        headers=headers,
        rows=rows,
        summary=f"{len(rows)} paused" if rows else "No paused requests",
        tips=tips if tips else None,
        truncate={"URL": {"max": 60, "mode": "middle"}},
    )


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _resume_desc or ""},
)
def resume(state, request: int, wait: float = 0.5, modifications: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Resume a paused request.

    For Request stage, can modify:
        url, method, headers, postData

    For Response stage, can modify:
        responseCode, responseHeaders

    Args:
        request: Request ID from network() table
        wait: Wait time for next event in seconds (default: 0.5)
        modifications: Request/response modifications dict
            - {"url": "..."} - Change URL
            - {"method": "POST"} - Change method
            - {"headers": [{"name": "X-Custom", "value": "test"}]} - Set headers
            - {"responseCode": 404} - Change response code
            - {"responseHeaders": [...]} - Modify response headers

    Examples:
        resume(583)                               # Simple resume
        resume(583, wait=1.0)                    # Wait for redirect
        resume(583, modifications={"url": "..."})  # Change URL
        resume(583, modifications={"method": "POST"})  # Change method
        resume(583, modifications={"headers": [{"name":"X-Custom","value":"test"}]})

    Returns:
        Continuation status with any follow-up events detected
    """
    # Get status to check if fetch is enabled
    status, error = rpc_call(state, "status")
    if error:
        return error
    if not status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Resume via RPC (now uses HAR ID)
    result, error = rpc_call(state, "fetch.resume", id=request, modifications=modifications, wait=wait)
    if error:
        return error

    # Build concise status line
    har_id = result.get("id", request)
    outcome = result.get("outcome", "unknown")
    resumed_from = result.get("resumed_from", "unknown")

    if outcome == "response":
        status_code = result.get("status", "?")
        summary = f"ID {har_id} → paused at Response ({status_code})"
    elif outcome == "redirect":
        redirect_id = result.get("redirect_id", "?")
        summary = f"ID {har_id} → redirected to ID {redirect_id}"
    elif outcome == "complete":
        summary = f"ID {har_id} → complete"
    else:
        summary = f"ID {har_id} → resumed from {resumed_from}"

    fields = {"Result": summary}
    if result.get("remaining", 0) > 0:
        fields["Remaining"] = f"{result['remaining']} paused"

    return info_response(title="Resumed", fields=fields)


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fail_desc or ""}
)
def fail(state, request: int, reason: str = "BlockedByClient") -> dict:
    """Fail a paused request.

    Args:
        request: Request ID from network() table
        reason: CDP error reason (default: BlockedByClient)
                Options: Failed, Aborted, TimedOut, AccessDenied,
                        ConnectionClosed, ConnectionReset, ConnectionRefused,
                        ConnectionAborted, ConnectionFailed, NameNotResolved,
                        InternetDisconnected, AddressUnreachable, BlockedByClient,
                        BlockedByResponse

    Examples:
        fail(583)                          # Fail specific request
        fail(583, reason="AccessDenied")  # Fail with specific reason

    Returns:
        Failure status
    """
    # Get status to check if fetch is enabled
    status, error = rpc_call(state, "status")
    if error:
        return error
    if not status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Fail via RPC (now uses HAR ID)
    result, error = rpc_call(state, "fetch.fail", id=request, reason=reason)
    if error:
        return error

    har_id = result.get("id", request)
    summary = f"ID {har_id} → failed ({reason})"

    fields = {"Result": summary}
    if result.get("remaining", 0) > 0:
        fields["Remaining"] = f"{result['remaining']} paused"

    return info_response(title="Failed", fields=fields)


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fulfill_desc or ""},
)
def fulfill(
    state,
    request: int,
    body: str = "",
    status: int = 200,
    headers: list = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Fulfill a paused request with a custom response.

    Returns a mock response without hitting the server. Useful for:
    - Mock API responses during development
    - Test error handling with specific status codes
    - Offline development without backend

    Args:
        request: Request ID from network() table
        body: Response body content (default: empty)
        status: HTTP status code (default: 200)
        headers: Response headers as list of {"name": "...", "value": "..."} dicts

    Examples:
        fulfill(583)                                    # Empty 200 response
        fulfill(583, body='{"ok": true}')              # JSON response
        fulfill(583, body="Not Found", status=404)     # Error response
        fulfill(583, headers=[{"name": "Content-Type", "value": "application/json"}])

    Returns:
        Fulfillment status
    """
    # Get status to check if fetch is enabled
    fetch_status, error = rpc_call(state, "status")
    if error:
        return error
    if not fetch_status.get("fetch", {}).get("enabled", False):
        return error_response("Fetch interception is disabled. Use fetch('enable') first.")

    # Fulfill via RPC (uses HAR ID)
    result, error = rpc_call(
        state,
        "fetch.fulfill",
        id=request,
        response_code=status,
        response_headers=headers,
        body=body,
    )
    if error:
        return error

    har_id = result.get("id", request)
    summary = f"ID {har_id} → fulfilled ({status})"

    fields = {"Result": summary}
    if result.get("remaining", 0) > 0:
        fields["Remaining"] = f"{result['remaining']} paused"

    return info_response(title="Fulfilled", fields=fields)


__all__ = ["fetch", "requests", "resume", "fail", "fulfill"]
