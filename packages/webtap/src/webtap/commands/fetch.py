"""HTTP fetch request interception and debugging commands.

PUBLIC API:
  - fetch: Enable/disable fetch interception for request debugging
  - requests: Show paused fetch requests
  - resume: Resume paused fetch requests with optional modifications
  - fail: Fail paused fetch requests with specified reason
"""

from webtap.app import app
from webtap.commands._errors import check_connection, error_response
from webtap.commands._utils import build_table_response, build_info_response
from webtap.commands._symbols import sym


@app.command(display="markdown")
def fetch(state, enable: bool | None = None, disable: bool = False, response: bool = False) -> dict:
    """Enable/disable fetch interception for request debugging.

    When enabled, requests pause for inspection.
    Use requests() to see paused items, resume() or fail() to proceed.

    Args:
        enable: Enable interception (True/False to set, None to show status)
        disable: Disable interception
        response: Also pause at Response stage (when enabling)

    Examples:
        fetch()                      # Show current status
        fetch(enable=True)           # Enable (Request stage only)
        fetch(enable=True, response=True)  # Enable both stages
        fetch(disable=True)          # Disable

    Returns:
        Fetch interception status
    """
    fetch_service = state.service.fetch

    # Handle disable
    if disable:
        result = fetch_service.disable()
        if "error" in result:
            return error_response("custom", custom_message=result["error"])
        return build_info_response(
            title=f"Fetch {sym('disabled')}", 
            fields={"Status": "Interception disabled"}
        )

    # Handle enable
    if enable is True:
        # Check connection first
        if error := check_connection(state):
            return error
            
        result = fetch_service.enable(state.cdp, response_stage=response)
        if "error" in result:
            return error_response("custom", custom_message=result["error"])
        return build_info_response(
            title=f"Fetch {sym('enabled')}", 
            fields={
                "Stages": result.get("stages", "Request stage only"),
                "Status": f"{sym('paused')} Requests will pause"
            }
        )
    elif enable is False:
        result = fetch_service.disable()
        if "error" in result:
            return error_response("custom", custom_message=result["error"])
        return build_info_response(
            title=f"Fetch {sym('disabled')}", 
            fields={"Status": "Interception disabled"}
        )

    # Show status
    status_symbol = sym("enabled") if fetch_service.enabled else sym("disabled")
    return build_info_response(
        title=f"Fetch Status {status_symbol}",
        fields={
            "Status": "Enabled" if fetch_service.enabled else "Disabled",
            "Paused": f"{sym('paused')} {fetch_service.paused_count} requests" if fetch_service.enabled else sym("none"),
        },
    )


@app.command(display="markdown")
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
        return error_response("fetch_disabled")

    rows = fetch_service.get_paused_list()

    # Apply limit
    if limit and len(rows) > limit:
        rows = rows[:limit]

    # Build warnings if needed
    warnings = []
    if limit and len(rows) == limit:
        warnings.append(f"Showing first {limit} paused requests (use limit parameter to see more)")

    # Build markdown response
    return build_table_response(
        title=f"{sym('paused')} Paused Requests",
        headers=["ID", "Stage", "Method", "Status", "URL"],
        rows=rows,
        summary=f"{sym('paused')} {len(rows)} paused requests",
        warnings=warnings,
    )


@app.command(display="markdown")
def resume(state, request: int, wait: float = 0.5, **modifications) -> dict:
    """Resume a paused request with optional modifications.

    For Request stage, can modify:
        url, method, headers, postData

    For Response stage, can modify:
        responseCode, responseHeaders

    Args:
        request: Row ID from requests() table (e.g., 47)
        wait: Seconds to wait for follow-up events (0 to disable)
        **modifications: Direct CDP parameters to modify

    Examples:
        resume(47)                                      # Resume as-is
        resume(47, wait=1.0)                           # Resume and wait longer for follow-up
        resume(47, wait=0)                             # Resume without waiting
        resume(47, url="https://modified.com")         # Change URL
        resume(47, method="POST")                      # Change method
        resume(47, headers=[{"name":"X-Custom","value":"test"}])

    Returns:
        Continuation status with any follow-up events detected
    """
    fetch_service = state.service.fetch

    if not fetch_service.enabled:
        return error_response("fetch_disabled")

    result = fetch_service.continue_request(request, modifications, wait_for_next=wait)

    if "error" in result:
        return error_response("custom", custom_message=result["error"])

    fields = {
        "Stage": result["stage"],
        "Continued": f"{sym('success')} Row {result['continued']}"
    }

    # Report follow-up if detected
    if next_event := result.get("next_event"):
        fields[f"{sym('arrow')} Next"] = next_event["description"]
        fields["Next ID"] = str(next_event["rowid"])
        if next_event.get("status"):
            fields["Status"] = next_event["status"]

    if result.get("remaining"):
        fields["Remaining"] = f"{sym('paused')} {result['remaining']} requests"

    return build_info_response(title=f"{sym('success')} Request Resumed", fields=fields)


@app.command(display="markdown")
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
        return error_response("fetch_disabled")

    result = fetch_service.fail_request(request, reason)

    if "error" in result:
        return error_response("custom", custom_message=result["error"])

    fields = {
        "Failed": f"{sym('error')} Row {result['failed']}", 
        "Reason": result["reason"]
    }
    if result.get("remaining") is not None:
        fields["Remaining"] = f"{sym('paused')} {result['remaining']} requests"

    return build_info_response(title=f"{sym('error')} Request Failed", fields=fields)
