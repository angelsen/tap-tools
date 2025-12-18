"""HTTP fetch request interception and debugging commands."""

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import error_response, info_response
from webtap.commands._tips import get_mcp_description, get_tips

_fetch_desc = get_mcp_description("fetch")
_resume_desc = get_mcp_description("resume")
_fail_desc = get_mcp_description("fail")
_fulfill_desc = get_mcp_description("fulfill")


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
    try:
        if action == "disable":
            state.client.call("fetch.disable")
            return info_response(title="Fetch Disabled", fields={"Status": "Interception disabled"})

        elif action == "enable":
            response_stage = (options or {}).get("response", False)
            result = state.client.call("fetch.enable", request=True, response=response_stage)

            stages = "Request and Response stages" if result.get("response_stage") else "Request stage only"
            return info_response(
                title="Fetch Enabled",
                fields={
                    "Stages": stages,
                    "Status": "Requests will pause",
                },
            )

        elif action == "status":
            status = state.client.call("status")
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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))


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
    try:
        # Get status to check if fetch is enabled
        status = state.client.call("status")
        if not status.get("fetch", {}).get("enabled", False):
            return error_response("Fetch interception is disabled. Use fetch('enable') first.")

        # Delegate to network command with state filter
        from webtap.commands.network import network

        result = network(state, req_state="paused", limit=limit, show_all=True)

        # Add fetch-specific tips if we have rows
        if result.get("elements"):
            # Find table element and extract first ID for tips
            for element in result["elements"]:
                if element.get("type") == "table":
                    rows = element.get("rows", [])
                    if rows and rows[0]:
                        example_id = rows[0].get("ID", 0)
                        tips = get_tips("requests", context={"id": example_id})
                        if tips:
                            # Add tips as alerts after table
                            tip_elements = [{"type": "alert", "content": tip, "level": "info"} for tip in tips]
                            # Insert after table
                            table_index = result["elements"].index(element)
                            result["elements"] = (
                                result["elements"][: table_index + 1]
                                + tip_elements
                                + result["elements"][table_index + 1 :]
                            )
                    break

        return result

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))


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
    try:
        # Get status to check if fetch is enabled
        status = state.client.call("status")
        if not status.get("fetch", {}).get("enabled", False):
            return error_response("Fetch interception is disabled. Use fetch('enable') first.")

        # Resume via RPC (now uses HAR ID)
        result = state.client.call("fetch.resume", id=request, modifications=modifications, wait=wait)

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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))


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
    try:
        # Get status to check if fetch is enabled
        status = state.client.call("status")
        if not status.get("fetch", {}).get("enabled", False):
            return error_response("Fetch interception is disabled. Use fetch('enable') first.")

        # Fail via RPC (now uses HAR ID)
        result = state.client.call("fetch.fail", id=request, reason=reason)

        har_id = result.get("id", request)
        summary = f"ID {har_id} → failed ({reason})"

        fields = {"Result": summary}
        if result.get("remaining", 0) > 0:
            fields["Remaining"] = f"{result['remaining']} paused"

        return info_response(title="Failed", fields=fields)

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))


@app.command(
    display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fulfill_desc or ""}
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
    try:
        # Get status to check if fetch is enabled
        fetch_status = state.client.call("status")
        if not fetch_status.get("fetch", {}).get("enabled", False):
            return error_response("Fetch interception is disabled. Use fetch('enable') first.")

        # Fulfill via RPC (uses HAR ID)
        result = state.client.call(
            "fetch.fulfill",
            id=request,
            response_code=status,
            response_headers=headers,
            body=body,
        )

        har_id = result.get("id", request)
        summary = f"ID {har_id} → fulfilled ({status})"

        fields = {"Result": summary}
        if result.get("remaining", 0) > 0:
            fields["Remaining"] = f"{result['remaining']} paused"

        return info_response(title="Fulfilled", fields=fields)

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))
