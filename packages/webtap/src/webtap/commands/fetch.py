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
def fetch(state, enable: bool | None = None, disable: bool = False) -> dict:
    """Enable/disable fetch interception for request debugging.

    When enabled, ALL requests and responses pause for inspection.
    Use requests() to see paused items, continue_() or fail() to proceed.

    Args:
        enable: Enable interception (True/False to set, None to show status)
        disable: Disable interception and continue all

    Examples:
        fetch()              # Show current status
        fetch(enable=True)   # Enable interception
        fetch(disable=True)  # Disable and continue all

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
            title="Fetch Disabled", fields={"Continued": f"{result.get('continued', 0)} requests"}
        )

    # Handle enable
    if enable is True:
        result = fetch_service.enable(state.cdp)
        if "error" in result:
            return error_response("custom", custom_message=result["error"])
        return build_info_response(title="Fetch Enabled", fields={"Status": "All requests will pause"})
    elif enable is False:
        result = fetch_service.disable()
        if "error" in result:
            return error_response("custom", custom_message=result["error"])
        return build_info_response(title="Fetch Disabled", fields={"Status": "Interception disabled"})

    # Show status
    return build_info_response(
        title="Fetch Status",
        fields={
            "Status": "Enabled" if fetch_service.enabled else "Disabled",
            "Paused": f"{fetch_service.paused_count} requests" if fetch_service.enabled else sym("empty"),
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
        title="Paused Requests",
        headers=["ID", "Stage", "Method", "Status", "URL"],
        rows=rows,
        summary=f"{len(rows)} paused requests",
        warnings=warnings,
    )


@app.command(display="markdown")
def resume(state, request: int | None = None, all: bool = False, wait: float = 0.5, **modifications) -> dict:
    """Resume paused request(s) with optional modifications.

    For Request stage, can modify:
        url, method, headers, postData

    For Response stage, can modify:
        responseCode, responseHeaders

    Args:
        request: Row ID from requests() table (e.g., 47)
        all: Continue all paused requests
        wait: Seconds to wait for follow-up requests (0 to disable)
        **modifications: Direct CDP parameters to modify

    Examples:
        resume(47)                                      # Resume as-is
        resume(47, wait=1.0)                           # Resume and wait for redirect
        resume(47, wait=0)                             # Resume without waiting
        resume(47, url="https://modified.com")         # Change URL
        resume(47, method="POST")                      # Change method
        resume(47, headers=[{"name":"X-Custom","value":"test"}])
        resume(all=True)                                 # Resume all

    Returns:
        Continuation status with any follow-up requests detected
    """
    fetch_service = state.service.fetch

    if not fetch_service.enabled:
        return error_response("fetch_disabled")

    # Continue all
    if all:
        result = fetch_service.continue_all()
        if "error" in result:
            return error_response("custom", custom_message=result["error"])

        fields = {"Continued": f"{result['continued']} requests"}
        if result.get("errors"):
            fields["Errors"] = ", ".join(result["errors"])

        return build_info_response(title="Resume All", fields=fields)

    # Resume specific request
    if not request:
        return error_response("custom", custom_message="Usage: resume(47) or resume(all=True)")

    result = fetch_service.continue_request(request, modifications, wait=wait)

    if "error" in result:
        return error_response("custom", custom_message=result["error"])

    fields = {"Stage": result["stage"], "Continued": result["continued"]}

    # Report follow-up if detected
    if follow_up := result.get("follow_up"):
        fields["Follow-up"] = f"Request {follow_up['rowid']}"
        if follow_up.get("status"):
            fields["Follow-up Status"] = follow_up["status"]
        if follow_up.get("url"):
            fields["Follow-up URL"] = follow_up["url"]

    if result.get("remaining"):
        fields["Remaining"] = f"{result['remaining']} requests"

    return build_info_response(title="Request Resumed", fields=fields)


@app.command(display="markdown")
def fail(state, request: int | None = None, all: bool = False, reason: str = "BlockedByClient") -> dict:
    """Fail paused request(s).

    Args:
        request: Row ID from requests() table
        all: Fail all paused requests
        reason: CDP error reason (default: BlockedByClient)
                Options: Failed, Aborted, TimedOut, AccessDenied,
                        ConnectionClosed, ConnectionReset, ConnectionRefused,
                        ConnectionAborted, ConnectionFailed, NameNotResolved,
                        InternetDisconnected, AddressUnreachable, BlockedByClient,
                        BlockedByResponse

    Examples:
        fail(47)                          # Fail specific request
        fail(47, reason="AccessDenied")  # Fail with specific reason
        fail(all=True)                    # Fail all paused

    Returns:
        Failure status
    """
    fetch_service = state.service.fetch

    if not fetch_service.enabled:
        return error_response("fetch_disabled")

    # Fail all
    if all:
        result = fetch_service.fail_all(reason)
        if "error" in result:
            return error_response("custom", custom_message=result["error"])

        fields = {"Failed": f"{result['failed']} requests", "Reason": reason}
        if result.get("errors"):
            fields["Errors"] = ", ".join(result["errors"])

        return build_info_response(title="Fail All", fields=fields)

    # Fail specific request
    if not request:
        return error_response("custom", custom_message="Usage: fail(47) or fail(all=True)")

    result = fetch_service.fail_request(request, reason)

    if "error" in result:
        return error_response("custom", custom_message=result["error"])

    fields = {"Failed": result["failed"], "Reason": result["reason"]}
    if result.get("remaining"):
        fields["Remaining"] = f"{result['remaining']} requests"

    return build_info_response(title="Request Failed", fields=fields)
