"""RPC method handlers - thin wrappers around WebTapService.

Handlers receive RPCContext and delegate to WebTapService for business logic.
State transitions are managed by the ConnectionMachine via ctx.machine.

Handler categories:
  - Connection Management: connect, disconnect, pages, status, clear
  - Browser Inspection: browser.startInspect, browser.stopInspect, browser.clear
  - Fetch Interception: fetch.enable, fetch.disable, fetch.resume, fetch.fail, fetch.fulfill
  - Data Queries: network, request, console
  - Filter Management: filters.*
  - Navigation: navigate, reload, back, forward, history, page
  - JavaScript: js
  - Other: cdp, errors.dismiss

PUBLIC API:
  - register_handlers: Register all RPC handlers with framework
  - CONNECTED_STATES: States where connected operations are valid
  - CONNECTED_ONLY: States where only connected (not inspecting) is valid
"""

from webtap.rpc.errors import ErrorCode, RPCError
from webtap.rpc.framework import RPCContext, RPCFramework

CONNECTED_STATES = ["connected", "inspecting"]
CONNECTED_ONLY = ["connected"]

__all__ = ["register_handlers", "CONNECTED_STATES", "CONNECTED_ONLY"]


def _resolve_cdp_session(ctx: RPCContext, target: str | None):
    """Resolve target to CDPSession.

    Args:
        ctx: RPC context
        target: Target ID or None for primary connection

    Returns:
        CDPSession instance

    Raises:
        RPCError: If target not found or multiple connections with no target specified
    """
    if target:
        conn = ctx.service.get_connection(target)
        if not conn:
            raise RPCError(ErrorCode.INVALID_PARAMS, f"Target '{target}' not found")
        return conn.cdp

    # No target specified - use primary connection
    if len(ctx.service.connections) > 1:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Multiple connections active. Specify target parameter.")

    return ctx.service.cdp


def register_handlers(rpc: RPCFramework) -> None:
    """Register all RPC handlers with the framework.

    Args:
        rpc: RPCFramework instance to register handlers with
    """
    rpc.method("connect")(connect)
    rpc.method("disconnect", requires_state=CONNECTED_STATES)(disconnect)
    rpc.method("pages", broadcasts=False)(pages)
    rpc.method("status", broadcasts=False)(status)
    rpc.method("clear", requires_state=CONNECTED_STATES)(clear)

    rpc.method("browser.startInspect", requires_state=CONNECTED_ONLY)(browser_start_inspect)
    rpc.method("browser.stopInspect", requires_state=["inspecting"])(browser_stop_inspect)
    rpc.method("browser.clear", requires_state=CONNECTED_STATES)(browser_clear)

    rpc.method("fetch.enable", requires_state=CONNECTED_STATES)(fetch_enable)
    rpc.method("fetch.disable", requires_state=CONNECTED_STATES)(fetch_disable)
    rpc.method("fetch.resume", requires_state=CONNECTED_STATES, requires_paused_request=True)(fetch_resume)
    rpc.method("fetch.fail", requires_state=CONNECTED_STATES, requires_paused_request=True)(fetch_fail)
    rpc.method("fetch.fulfill", requires_state=CONNECTED_STATES, requires_paused_request=True)(fetch_fulfill)

    rpc.method("network", requires_state=CONNECTED_STATES, broadcasts=False)(network)
    rpc.method("request", requires_state=CONNECTED_STATES, broadcasts=False)(request)
    rpc.method("console", requires_state=CONNECTED_STATES, broadcasts=False)(console)

    rpc.method("filters.status", broadcasts=False)(filters_status)
    rpc.method("filters.add")(filters_add)
    rpc.method("filters.remove")(filters_remove)
    rpc.method("filters.enable", requires_state=CONNECTED_STATES)(filters_enable)
    rpc.method("filters.disable", requires_state=CONNECTED_STATES)(filters_disable)
    rpc.method("filters.enableAll", requires_state=CONNECTED_STATES)(filters_enable_all)
    rpc.method("filters.disableAll", requires_state=CONNECTED_STATES)(filters_disable_all)

    rpc.method("navigate", requires_state=CONNECTED_STATES)(navigate)
    rpc.method("reload", requires_state=CONNECTED_STATES)(reload)
    rpc.method("back", requires_state=CONNECTED_STATES)(back)
    rpc.method("forward", requires_state=CONNECTED_STATES)(forward)
    rpc.method("history", requires_state=CONNECTED_STATES, broadcasts=False)(history)
    rpc.method("page", requires_state=CONNECTED_STATES, broadcasts=False)(page)

    rpc.method("js", requires_state=CONNECTED_STATES)(js)

    rpc.method("cdp", requires_state=CONNECTED_STATES)(cdp)
    rpc.method("errors.dismiss")(errors_dismiss)

    # Multi-target support
    rpc.method("targets.set")(targets_set)
    rpc.method("targets.clear")(targets_clear)
    rpc.method("targets.get", broadcasts=False)(targets_get)

    # Port management
    rpc.method("ports.add")(ports_add)
    rpc.method("ports.remove")(ports_remove)


def connect(
    ctx: RPCContext,
    page_id: str | None = None,
    page: int | None = None,
    chrome_port: int | None = None,
    target: str | None = None,
) -> dict:
    """Connect to a Chrome page (supports multi-target).

    Args:
        page_id: Chrome page ID. Defaults to None.
        page: Page index. Defaults to None.
        chrome_port: Chrome debug port to connect to (default: 9222). Defaults to None.
        target: Target ID to connect to (format: "{port}:{short-id}"). Defaults to None.

    Returns:
        Connection result with page details including 'target'.

    Raises:
        RPCError: If connection fails or invalid parameters.
    """
    # Validate parameters
    param_count = sum(x is not None for x in [page, page_id, target])
    if param_count == 0:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Must specify 'page', 'page_id', or 'target'")
    if param_count > 1:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Can only specify one of 'page', 'page_id', or 'target'")

    # Check and auto-update extension before connecting
    from webtap.services.setup.extension import auto_update_extension
    from webtap.services.setup.platform import get_platform_info

    try:
        ext_status = auto_update_extension()

        # Add appropriate notices based on extension status
        if ext_status.status == "missing":
            # Extension was just installed
            info = get_platform_info()
            extension_path = info["paths"]["data_dir"] / "extension"
            ctx.service.notices.add("extension_installed", path=str(extension_path))

        elif ext_status.status == "manifest_changed":
            # Manifest changed - requires reload in chrome://extensions
            ctx.service.notices.add("extension_manifest_changed")

        elif ext_status.status == "outdated":
            # Non-manifest files changed - requires sidepanel reopen
            ctx.service.notices.add("extension_updated")

        # If status was "ok", no notice needed

    except Exception as e:
        # Log error but don't block connection
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Extension check failed: {e}")

    ctx.machine.start_connect()

    try:
        result = ctx.service.connect_to_page(page_index=page, page_id=page_id, chrome_port=chrome_port, target=target)
        ctx.machine.connect_success()
        return {"connected": True, **result}

    except Exception as e:
        ctx.machine.connect_failed()
        raise RPCError(ErrorCode.NOT_CONNECTED, str(e))


def disconnect(ctx: RPCContext, target: str | None = None) -> dict:
    """Disconnect from target(s).

    Args:
        target: Target ID to disconnect. If None, disconnects all targets.

    Returns:
        Dict with 'disconnected' list of target IDs.
    """
    ctx.machine.start_disconnect()

    try:
        if target:
            # Disconnect specific target
            ctx.service.disconnect_target(target)
            disconnected = [target]
        else:
            # Disconnect all targets
            disconnected = list(ctx.service.connections.keys())
            ctx.service.disconnect()

        ctx.machine.disconnect_complete()
        return {"disconnected": disconnected}

    except Exception as e:
        # Still complete the transition even if there's an error
        ctx.machine.disconnect_complete()
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def pages(ctx: RPCContext, chrome_port: int | None = None) -> dict:
    """Get available Chrome pages from one or all tracked ports.

    Args:
        chrome_port: Specific port to query. If None, returns pages from all tracked ports.

    Returns:
        Dict with 'pages' list. Each page includes 'chrome_port' and 'is_connected' fields.
    """
    try:
        return ctx.service.list_pages(chrome_port=chrome_port)
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Failed to list pages: {e}")


def status(ctx: RPCContext) -> dict:
    """Get comprehensive status including connection, events, browser, and fetch details."""
    from webtap.api.state import get_full_state

    return get_full_state()


def clear(ctx: RPCContext, events: bool = True, console: bool = False) -> dict:
    """Clear various data stores.

    Args:
        events: Clear CDP events. Defaults to True.
        console: Clear browser console. Defaults to False.
    """
    cleared = []

    if events:
        ctx.service.cdp.clear_events()
        cleared.append("events")

    if console:
        if ctx.service.cdp.is_connected:
            success = ctx.service.console.clear_browser_console()
            if success:
                cleared.append("console")
        else:
            cleared.append("console (not connected)")

    return {"cleared": cleared}


def browser_start_inspect(ctx: RPCContext) -> dict:
    """Enable CDP element inspection mode."""
    ctx.machine.start_inspect()
    result = ctx.service.dom.start_inspect()
    return {**result}


def browser_stop_inspect(ctx: RPCContext) -> dict:
    """Disable CDP element inspection mode."""
    ctx.machine.stop_inspect()
    result = ctx.service.dom.stop_inspect()
    return {**result}


def browser_clear(ctx: RPCContext) -> dict:
    """Clear all element selections."""
    ctx.service.dom.clear_selections()
    return {"success": True, "selections": {}}


def fetch_enable(ctx: RPCContext, request: bool = True, response: bool = False) -> dict:
    """Enable fetch request interception."""
    result = ctx.service.fetch.enable(ctx.service.cdp, response_stage=response)
    return {**result}


def fetch_disable(ctx: RPCContext) -> dict:
    """Disable fetch request interception."""
    result = ctx.service.fetch.disable()
    return {**result}


def fetch_resume(ctx: RPCContext, id: int, paused: dict, modifications: dict | None = None, wait: float = 0.5) -> dict:
    """Resume a paused request.

    Args:
        id: Request ID from network()
        paused: Paused request dict (injected by framework)
        modifications: Optional request/response modifications. Defaults to None.
        wait: Wait time for follow-up events. Defaults to 0.5.
    """
    try:
        result = ctx.service.fetch.continue_request(paused["rowid"], modifications, wait)

        response = {
            "id": id,
            "resumed_from": result["resumed_from"],
            "outcome": result["outcome"],
            "remaining": result["remaining"],
        }

        if result.get("status"):
            response["status"] = result["status"]

        # For redirects, lookup new HAR ID
        if result.get("redirect_request_id"):
            new_har = ctx.service.cdp.query(
                "SELECT id FROM har_summary WHERE request_id = ? LIMIT 1",
                [result["redirect_request_id"]],
            )
            if new_har:
                response["redirect_id"] = new_har[0][0]

        return response
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def fetch_fail(ctx: RPCContext, id: int, paused: dict, reason: str = "BlockedByClient") -> dict:
    """Fail a paused request.

    Args:
        id: Request ID from network()
        paused: Paused request dict (injected by framework)
        reason: CDP error reason. Defaults to "BlockedByClient".
    """
    try:
        result = ctx.service.fetch.fail_request(paused["rowid"], reason)
        return {
            "id": id,
            "outcome": "failed",
            "reason": reason,
            "remaining": result.get("remaining", 0),
        }
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def fetch_fulfill(
    ctx: RPCContext,
    id: int,
    paused: dict,
    response_code: int = 200,
    response_headers: list[dict[str, str]] | None = None,
    body: str = "",
) -> dict:
    """Fulfill a paused request with a custom response.

    Args:
        id: Request ID from network()
        paused: Paused request dict (injected by framework)
        response_code: HTTP status code. Defaults to 200.
        response_headers: Response headers. Defaults to None.
        body: Response body. Defaults to "".
    """
    try:
        result = ctx.service.fetch.fulfill_request(paused["rowid"], response_code, response_headers, body)
        return {
            "id": id,
            "outcome": "fulfilled",
            "response_code": response_code,
            "remaining": result.get("remaining", 0),
        }
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def network(
    ctx: RPCContext,
    limit: int = 50,
    status: int | None = None,
    method: str | None = None,
    resource_type: str | None = None,
    url: str | None = None,
    state: str | None = None,
    show_all: bool = False,
    order: str = "desc",
) -> dict:
    """Query network requests with inline filters.

    Args:
        limit: Maximum number of requests to return. Defaults to 50.
        status: Filter by HTTP status code. Defaults to None.
        method: Filter by HTTP method. Defaults to None.
        resource_type: Filter by resource type. Defaults to None.
        url: Filter by URL pattern. Defaults to None.
        state: Filter by request state. Defaults to None.
        show_all: Show all requests without filter groups. Defaults to False.
        order: Sort order ("asc" or "desc"). Defaults to "desc".
    """
    requests = ctx.service.network.get_requests(
        limit=limit,
        status=status,
        method=method,
        type_filter=resource_type,
        url=url,
        state=state,
        apply_groups=not show_all,
        order=order,
    )
    return {"requests": requests}


def request(ctx: RPCContext, id: int, fields: list[str] | None = None) -> dict:
    """Get request details with field selection.

    Args:
        id: Request ID from network()
        fields: List of fields to extract. Defaults to None.
    """
    entry = ctx.service.network.get_request_details(id)
    if not entry:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Request {id} not found")

    selected = ctx.service.network.select_fields(entry, fields)
    return {"entry": selected}


def console(ctx: RPCContext, limit: int = 50, level: str | None = None) -> dict:
    """Get console messages.

    Args:
        limit: Maximum number of messages to return. Defaults to 50.
        level: Filter by console level. Defaults to None.
    """
    rows = ctx.service.console.get_recent_messages(limit=limit, level=level)

    messages = []
    for row in rows:
        rowid, msg_level, source, message, timestamp = row
        messages.append(
            {
                "id": rowid,
                "level": msg_level or "log",
                "source": source or "console",
                "message": message or "",
                "timestamp": float(timestamp) if timestamp else None,
            }
        )

    return {"messages": messages}


def filters_status(ctx: RPCContext) -> dict:
    """Get all filter groups with enabled status."""
    return ctx.service.filters.get_status()


def filters_add(ctx: RPCContext, name: str, hide: dict) -> dict:
    """Add a new filter group."""
    ctx.service.filters.add(name, hide)
    return {"added": True, "name": name}


def filters_remove(ctx: RPCContext, name: str) -> dict:
    """Remove a filter group."""
    result = ctx.service.filters.remove(name)
    if result:
        return {"removed": True, "name": name}
    return {"removed": False, "name": name}


def filters_enable(ctx: RPCContext, name: str) -> dict:
    """Enable a filter group."""
    result = ctx.service.filters.enable(name)
    if result:
        return {"enabled": True, "name": name}
    raise RPCError(ErrorCode.INVALID_PARAMS, f"Group '{name}' not found")


def filters_disable(ctx: RPCContext, name: str) -> dict:
    """Disable a filter group."""
    result = ctx.service.filters.disable(name)
    if result:
        return {"disabled": True, "name": name}
    raise RPCError(ErrorCode.INVALID_PARAMS, f"Group '{name}' not found")


def filters_enable_all(ctx: RPCContext) -> dict:
    """Enable all filter groups."""
    fm = ctx.service.filters
    for name in fm.groups:
        fm.enable(name)
    return {"enabled": list(fm.enabled)}


def filters_disable_all(ctx: RPCContext) -> dict:
    """Disable all filter groups."""
    fm = ctx.service.filters
    fm.enabled.clear()
    return {"enabled": []}


def cdp(ctx: RPCContext, command: str, params: dict | None = None) -> dict:
    """Execute arbitrary CDP command."""
    try:
        result = ctx.service.cdp.execute(command, params or {})
        return {"result": result}
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def errors_dismiss(ctx: RPCContext) -> dict:
    """Dismiss the current error."""
    ctx.service.state.error_state = None
    return {"success": True}


def navigate(ctx: RPCContext, url: str, target: str | None = None) -> dict:
    """Navigate to URL.

    Args:
        url: Target URL
        target: Target ID. Uses primary connection if not specified.
    """
    try:
        cdp = _resolve_cdp_session(ctx, target)
        result = cdp.execute("Page.navigate", {"url": url})
        return {
            "url": url,
            "frame_id": result.get("frameId"),
            "loader_id": result.get("loaderId"),
            "error": result.get("errorText"),
        }
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Navigation failed: {e}")


def reload(ctx: RPCContext, ignore_cache: bool = False, target: str | None = None) -> dict:
    """Reload current page.

    Args:
        ignore_cache: Ignore browser cache. Defaults to False.
        target: Target ID. Uses primary connection if not specified.
    """
    try:
        cdp = _resolve_cdp_session(ctx, target)
        cdp.execute("Page.reload", {"ignoreCache": ignore_cache})
        return {"reloaded": True, "ignore_cache": ignore_cache}
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Reload failed: {e}")


def back(ctx: RPCContext, target: str | None = None) -> dict:
    """Navigate back in history.

    Args:
        target: Target ID. Uses primary connection if not specified.
    """
    try:
        return _navigate_history(ctx, -1, target)
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Back navigation failed: {e}")


def forward(ctx: RPCContext, target: str | None = None) -> dict:
    """Navigate forward in history.

    Args:
        target: Target ID. Uses primary connection if not specified.
    """
    try:
        return _navigate_history(ctx, +1, target)
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Forward navigation failed: {e}")


def _navigate_history(ctx: RPCContext, direction: int, target: str | None = None) -> dict:
    """Navigate history by direction.

    Args:
        direction: -1 for back, +1 for forward
        target: Target ID or None for primary connection
    """
    cdp = _resolve_cdp_session(ctx, target)
    result = cdp.execute("Page.getNavigationHistory", {})
    entries = result.get("entries", [])
    current = result.get("currentIndex", 0)
    target_idx = current + direction

    if target_idx < 0:
        return {"navigated": False, "reason": "Already at first entry"}
    if target_idx >= len(entries):
        return {"navigated": False, "reason": "Already at last entry"}

    target_entry = entries[target_idx]
    cdp.execute("Page.navigateToHistoryEntry", {"entryId": target_entry["id"]})

    return {
        "navigated": True,
        "title": target_entry.get("title", ""),
        "url": target_entry.get("url", ""),
        "index": target_idx,
        "total": len(entries),
    }


def history(ctx: RPCContext) -> dict:
    """Get navigation history."""
    try:
        result = ctx.service.cdp.execute("Page.getNavigationHistory", {})
        entries = result.get("entries", [])
        current = result.get("currentIndex", 0)

        return {
            "entries": [
                {
                    "id": e.get("id"),
                    "url": e.get("url", ""),
                    "title": e.get("title", ""),
                    "type": e.get("transitionType", ""),
                    "current": i == current,
                }
                for i, e in enumerate(entries)
            ],
            "current_index": current,
        }
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"History failed: {e}")


def page(ctx: RPCContext) -> dict:
    """Get current page info with title from DOM."""
    try:
        result = ctx.service.cdp.execute("Page.getNavigationHistory", {})
        entries = result.get("entries", [])
        current_index = result.get("currentIndex", 0)

        if not entries or current_index >= len(entries):
            return {"url": "", "title": "", "id": None, "type": ""}

        current = entries[current_index]

        try:
            title_result = ctx.service.cdp.execute(
                "Runtime.evaluate", {"expression": "document.title", "returnByValue": True}
            )
            title = title_result.get("result", {}).get("value", current.get("title", ""))
        except Exception:
            title = current.get("title", "")

        return {
            "url": current.get("url", ""),
            "title": title or "Untitled",
            "id": current.get("id"),
            "type": current.get("transitionType", ""),
        }
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Page info failed: {e}")


def js(
    ctx: RPCContext,
    code: str,
    selection: int | None = None,
    persist: bool = False,
    await_promise: bool = False,
    return_value: bool = True,
    target: str | None = None,
) -> dict:
    """Execute JavaScript in browser context.

    Args:
        code: JavaScript code to execute
        selection: Browser selection number to bind to 'element' variable. Defaults to None.
        persist: Keep variables in global scope. Defaults to False.
        await_promise: Await promise results. Defaults to False.
        return_value: Return the result value. Defaults to True.
        target: Target ID. Uses primary connection if not specified.
    """
    try:
        cdp = _resolve_cdp_session(ctx, target)

        if selection is not None:
            dom_state = ctx.service.dom.get_state()
            selections = dom_state.get("selections", {})
            sel_key = str(selection)

            if sel_key not in selections:
                available = ", ".join(selections.keys()) if selections else "none"
                raise RPCError(ErrorCode.INVALID_PARAMS, f"Selection #{selection} not found. Available: {available}")

            js_path = selections[sel_key].get("jsPath")
            if not js_path:
                raise RPCError(ErrorCode.INVALID_PARAMS, f"Selection #{selection} has no jsPath")

            # Wrap with element binding (always fresh scope for selection)
            code = f"(() => {{ const element = {js_path}; return ({code}); }})()"

        elif not persist:
            # Default: wrap in IIFE for fresh scope
            code = f"(() => {{ return ({code}); }})()"

        result = cdp.execute(
            "Runtime.evaluate",
            {
                "expression": code,
                "awaitPromise": await_promise,
                "returnByValue": return_value,
            },
        )

        if result.get("exceptionDetails"):
            exception = result["exceptionDetails"]
            error_text = exception.get("exception", {}).get("description", str(exception))
            raise RPCError(ErrorCode.INTERNAL_ERROR, f"JavaScript error: {error_text}")

        if return_value:
            value = result.get("result", {}).get("value")
            return {"value": value, "executed": True}
        else:
            return {"executed": True}

    except RPCError:
        raise
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"JS execution failed: {e}")


def targets_set(ctx: RPCContext, targets: list[str]) -> dict:
    """Set active targets for filtering.

    Args:
        targets: List of target IDs to filter to. Empty list = all targets.

    Returns:
        Dict with 'active_targets' list.
    """
    ctx.service.filters.set_targets(targets)
    return {"active_targets": targets}


def targets_clear(ctx: RPCContext) -> dict:
    """Clear active targets (show all).

    Returns:
        Dict with empty 'active_targets' list.
    """
    ctx.service.filters.clear_targets()
    return {"active_targets": []}


def targets_get(ctx: RPCContext) -> dict:
    """Get current active targets.

    Returns:
        Dict with 'active_targets' list (empty = all targets).
    """
    return {"active_targets": ctx.service.filters.get_targets()}


# Port management


def ports_add(ctx: RPCContext, port: int) -> dict:
    """Register a Chrome debug port with the daemon.

    Args:
        port: Chrome debug port number to register

    Returns:
        Dict with 'port', 'status', and optional 'warning'

    Raises:
        RPCError: If port validation fails
    """
    import httpx

    # Validate port range
    if not (1024 <= port <= 65535):
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Invalid port: {port}. Must be 1024-65535")

    # Check if Chrome is listening on this port
    try:
        response = httpx.get(f"http://localhost:{port}/json", timeout=2.0)
        if response.status_code != 200:
            return {
                "port": port,
                "status": "unreachable",
                "warning": f"Port {port} not responding with Chrome debug protocol",
            }
    except httpx.RequestError:
        return {
            "port": port,
            "status": "unreachable",
            "warning": f"Port {port} not responding. Is Chrome running with --remote-debugging-port={port}?",
        }

    # Create CDPSession for this port if it doesn't exist
    from webtap.cdp import CDPSession

    if hasattr(ctx.service.state, "cdp_sessions"):
        if port not in ctx.service.state.cdp_sessions:
            ctx.service.state.cdp_sessions[port] = CDPSession(port=port)

    return {"port": port, "status": "registered"}


def ports_remove(ctx: RPCContext, port: int) -> dict:
    """Unregister a port from daemon tracking.

    Args:
        port: Chrome debug port number to unregister

    Returns:
        Dict with 'port' and 'removed' boolean

    Raises:
        RPCError: If port is protected or not found
    """
    # Protect default port 9222
    if port == 9222:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Port 9222 is protected (default desktop port)")

    if not hasattr(ctx.service.state, "cdp_sessions"):
        raise RPCError(ErrorCode.INTERNAL_ERROR, "Daemon state not available")

    if port not in ctx.service.state.cdp_sessions:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Port {port} not registered")

    # Disconnect any active connections on this port
    from webtap.targets import parse_target

    targets_to_disconnect = []
    for target_id in ctx.service.connections:
        target_port, _ = parse_target(target_id)
        if target_port == port:
            targets_to_disconnect.append(target_id)

    for target_id in targets_to_disconnect:
        ctx.service.disconnect_target(target_id)

    # Remove the CDPSession
    cdp_session = ctx.service.state.cdp_sessions.pop(port, None)
    if cdp_session:
        cdp_session.cleanup()

    return {"port": port, "removed": True, "disconnected": targets_to_disconnect}
