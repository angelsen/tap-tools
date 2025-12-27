"""RPC method handlers - thin wrappers around WebTapService.

Handlers receive RPCContext and delegate to WebTapService for business logic.
State transitions are managed by the ConnectionMachine via ctx.machine.
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
        target: Target ID or None for single connection

    Returns:
        CDPSession instance

    Raises:
        RPCError: If target not found, no connections, or multiple connections without target
    """
    if target:
        conn = ctx.service.get_connection(target)
        if not conn:
            raise RPCError(ErrorCode.INVALID_PARAMS, f"Target '{target}' not found")
        return conn.cdp

    # No target specified - must have exactly one connection
    if len(ctx.service.connections) == 0:
        raise RPCError(ErrorCode.NOT_CONNECTED, "No connections active")
    if len(ctx.service.connections) > 1:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Multiple connections active. Specify target parameter.")

    # Return the only connection's CDPSession
    return next(iter(ctx.service.connections.values())).cdp


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
    rpc.method("entry", requires_state=CONNECTED_STATES, broadcasts=False)(entry)

    rpc.method("filters.status", broadcasts=False)(filters_status)
    rpc.method("filters.add", broadcasts=False)(filters_add)
    rpc.method("filters.remove", broadcasts=False)(filters_remove)
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

    rpc.method("js")(js)

    rpc.method("cdp", requires_state=CONNECTED_STATES)(cdp)
    rpc.method("errors.dismiss")(errors_dismiss)

    # Multi-target support
    rpc.method("targets.set")(targets_set)
    rpc.method("targets.clear")(targets_clear)
    rpc.method("targets.get", broadcasts=False)(targets_get)

    # Port management
    rpc.method("ports.add", broadcasts=False)(ports_add)
    rpc.method("ports.remove", broadcasts=False)(ports_remove)
    rpc.method("ports.list", broadcasts=False)(ports_list)


def connect(ctx: RPCContext, target: str) -> dict:
    """Connect to a Chrome page by target ID.

    Args:
        target: Target ID in format "port:short_id" (e.g., "9222:f8134d", "9224:24")

    Returns:
        Connection result with page details including 'target'.

    Raises:
        RPCError: If connection fails or target not found.
    """
    # Only transition global machine on first connection
    is_first_connection = len(ctx.service.connections) == 0

    if is_first_connection:
        # Guard: reject if already connecting (prevents state machine error)
        if not ctx.machine.may_start_connect():
            raise RPCError(ErrorCode.INVALID_STATE, f"Cannot connect: already in state '{ctx.machine.state}'")
        ctx.machine.start_connect()

    try:
        result = ctx.service.connect_to_page(target=target)

        if is_first_connection:
            ctx.machine.connect_success()

        return {"connected": True, **result}

    except Exception as e:
        if is_first_connection:
            ctx.machine.connect_failed()
        raise RPCError(ErrorCode.NOT_CONNECTED, str(e))


def disconnect(ctx: RPCContext, target: str | None = None) -> dict:
    """Disconnect from target(s).

    Args:
        target: Target ID to disconnect. If None, disconnects all targets.

    Returns:
        Dict with 'disconnected' list of target IDs.
    """
    try:
        if target:
            # Disconnect specific target
            ctx.service.disconnect_target(target)
            disconnected = [target]
        else:
            # Disconnect all targets
            ctx.machine.start_disconnect()
            disconnected = list(ctx.service.connections.keys())
            ctx.service.disconnect()
            ctx.machine.disconnect_complete()

        # Transition to disconnected only if no connections remain
        if len(ctx.service.connections) == 0 and ctx.machine.state != "disconnected":
            ctx.machine.force_disconnect()

        return {"disconnected": disconnected}

    except Exception as e:
        # Still complete the transition even if there's an error
        if ctx.machine.state == "disconnecting":
            ctx.machine.disconnect_complete()
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def pages(ctx: RPCContext) -> dict:
    """Get available Chrome pages from all tracked ports.

    Returns:
        Dict with 'pages' list. Each page includes 'target' and 'is_connected' fields.
    """
    try:
        return ctx.service.list_pages()
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Failed to list pages: {e}")


def status(ctx: RPCContext) -> dict:
    """Get comprehensive status including connection, events, browser, and fetch details."""
    from webtap.api.state import get_full_state

    return get_full_state()


def clear(ctx: RPCContext, events: bool = True, console: bool = False) -> dict:
    """Clear various data stores.

    Args:
        events: Clear CDP events from all connections. Defaults to True.
        console: Clear browser console. Defaults to False.
    """
    cleared = []

    if events:
        # Clear events from all connections
        for conn in ctx.service.connections.values():
            try:
                conn.cdp.clear_events()
            except Exception:
                pass
        cleared.append("events")

    if console:
        if ctx.service.connections:
            success = ctx.service.console.clear_browser_console()
            if success:
                cleared.append("console")
        else:
            cleared.append("console (not connected)")

    return {"cleared": cleared}


def browser_start_inspect(ctx: RPCContext, target: str) -> dict:
    """Enable CDP element inspection mode on a specific target.

    Args:
        target: Required. Target ID to inspect.

    Raises:
        RPCError: If target is not connected.
    """
    # Validate target exists
    if target not in ctx.service.connections:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Target '{target}' not connected")

    ctx.machine.start_inspect()
    result = ctx.service.dom.start_inspect(target)
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
    """Enable fetch request interception on all connected targets."""
    result = ctx.service.fetch.enable(response_stage=response)
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
        target = paused.get("target", "")
        result = ctx.service.fetch.continue_request(paused["rowid"], target, modifications, wait)

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
            har_id = ctx.service.network.get_har_id_by_request_id(result["redirect_request_id"], target)
            if har_id:
                response["redirect_id"] = har_id

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
        target = paused.get("target", "")
        result = ctx.service.fetch.fail_request(paused["rowid"], target, reason)
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
        target = paused.get("target", "")
        result = ctx.service.fetch.fulfill_request(paused["rowid"], target, response_code, response_headers, body)
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
    target: str | list[str] | None = None,
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
        target: Filter by target ID (single or list). Defaults to None.
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
        target=target,
    )
    return {"requests": requests}


def request(ctx: RPCContext, id: int, target: str | None = None, fields: list[str] | None = None) -> dict:
    """Get request details with field selection.

    Args:
        id: Request ID from network()
        target: Target ID for multi-target support.
        fields: List of fields to extract. Defaults to None.
    """
    entry = ctx.service.network.get_request_details(id, target=target)
    if not entry:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Request {id} not found")

    selected = ctx.service.network.select_fields(entry, fields)
    return {"entry": selected}


def console(ctx: RPCContext, limit: int = 50, level: str | None = None, target: str | list[str] | None = None) -> dict:
    """Get console messages.

    Args:
        limit: Maximum number of messages to return. Defaults to 50.
        level: Filter by console level. Defaults to None.
        target: Filter by target ID (single or list). Defaults to None.
    """
    rows = ctx.service.console.get_recent_messages(limit=limit, level=level, target=target)

    messages = []
    for row in rows:
        rowid, msg_level, source, message, timestamp, row_target = row
        messages.append(
            {
                "id": rowid,
                "level": msg_level or "log",
                "source": source or "console",
                "message": message or "",
                "timestamp": float(timestamp) if timestamp else None,
                "target": row_target,
            }
        )

    return {"messages": messages}


def entry(ctx: RPCContext, id: int, fields: list[str] | None = None) -> dict:
    """Get console entry details with field selection.

    Args:
        id: Console entry row ID from console() output
        fields: Field patterns for selection. None=minimal, ["*"]=all
    """
    entry_data = ctx.service.console.get_entry_details(id)
    if not entry_data:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Console entry {id} not found")

    selected = ctx.service.console.select_fields(entry_data, fields)
    return {"entry": selected}


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
    ctx.service.filters.disable_all()
    return {"enabled": []}


def cdp(ctx: RPCContext, command: str, params: dict | None = None, target: str | None = None) -> dict:
    """Execute arbitrary CDP command.

    Args:
        command: CDP command to execute (e.g., "Page.navigate")
        params: Command parameters. Defaults to None.
        target: Target ID. Required if multiple connections active.
    """
    try:
        cdp_session = _resolve_cdp_session(ctx, target)
        result = cdp_session.execute(command, params or {})
        return {"result": result}
    except RPCError:
        raise
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def errors_dismiss(ctx: RPCContext) -> dict:
    """Dismiss the current error."""
    ctx.service.clear_error()
    return {"success": True}


def navigate(ctx: RPCContext, url: str, target: str) -> dict:
    """Navigate to URL.

    Args:
        url: Target URL
        target: Target ID
    """
    try:
        result = ctx.service.execute_on_target(target, lambda cdp: cdp.execute("Page.navigate", {"url": url}))
        return {
            "url": url,
            "frame_id": result.get("frameId"),
            "loader_id": result.get("loaderId"),
            "error": result.get("errorText"),
        }
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Navigation failed: {e}")


def reload(ctx: RPCContext, target: str, ignore_cache: bool = False) -> dict:
    """Reload current page.

    Args:
        target: Target ID
        ignore_cache: Ignore browser cache. Defaults to False.
    """
    try:
        ctx.service.execute_on_target(target, lambda cdp: cdp.execute("Page.reload", {"ignoreCache": ignore_cache}))
        return {"reloaded": True, "ignore_cache": ignore_cache}
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Reload failed: {e}")


def back(ctx: RPCContext, target: str) -> dict:
    """Navigate back in history.

    Args:
        target: Target ID
    """
    try:
        return ctx.service.execute_on_target(target, lambda cdp: _navigate_history_impl(cdp, -1))
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Back navigation failed: {e}")


def forward(ctx: RPCContext, target: str) -> dict:
    """Navigate forward in history.

    Args:
        target: Target ID
    """
    try:
        return ctx.service.execute_on_target(target, lambda cdp: _navigate_history_impl(cdp, +1))
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Forward navigation failed: {e}")


def _navigate_history_impl(cdp, direction: int) -> dict:
    """Implementation of history navigation for a given CDP session.

    Args:
        cdp: CDPSession instance
        direction: -1 for back, +1 for forward
    """
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


def history(ctx: RPCContext, target: str | None = None) -> dict:
    """Get navigation history.

    Args:
        target: Target ID. Required if multiple connections active.
    """
    try:
        cdp_session = _resolve_cdp_session(ctx, target)
        result = cdp_session.execute("Page.getNavigationHistory", {})
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
    except RPCError:
        raise
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"History failed: {e}")


def page(ctx: RPCContext, target: str | None = None) -> dict:
    """Get current page info with title from DOM.

    Args:
        target: Target ID. Required if multiple connections active.
    """
    try:
        cdp_session = _resolve_cdp_session(ctx, target)
        result = cdp_session.execute("Page.getNavigationHistory", {})
        entries = result.get("entries", [])
        current_index = result.get("currentIndex", 0)

        if not entries or current_index >= len(entries):
            return {"url": "", "title": "", "id": None, "type": ""}

        current = entries[current_index]

        try:
            title_result = cdp_session.execute(
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
    except RPCError:
        raise
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Page info failed: {e}")


def js(
    ctx: RPCContext,
    code: str,
    target: str,
    selection: int | None = None,
    persist: bool = False,
    await_promise: bool = False,
    return_value: bool = True,
) -> dict:
    """Execute JavaScript in browser context.

    Args:
        code: JavaScript code to execute
        target: Target ID
        selection: Browser selection number to bind to 'element' variable. Defaults to None.
        persist: Keep variables in global scope. Defaults to False.
        await_promise: Await promise results. Defaults to False.
        return_value: Return the result value. Defaults to True.
    """
    try:
        return ctx.service.execute_on_target(
            target, lambda cdp: _execute_js(ctx, cdp, code, selection, persist, await_promise, return_value)
        )
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except RPCError:
        raise
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def _execute_js(ctx, cdp, code, selection, persist, await_promise, return_value) -> dict:
    """Implementation of JavaScript execution for a given CDP session."""
    if selection is not None and persist:
        raise RPCError(
            ErrorCode.INVALID_PARAMS,
            "Cannot use selection with persist=True. "
            "For element operations with global state, store element manually: "
            "js(target, \"window.el = document.querySelector('...')\", persist=True)",
        )

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

        code = f"const element = {js_path};\n{code}"

    result = cdp.execute(
        "Runtime.evaluate",
        {
            "expression": code,
            "awaitPromise": await_promise,
            "returnByValue": return_value,
            "replMode": not persist,
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


def targets_set(ctx: RPCContext, targets: list[str]) -> dict:
    """Set tracked targets for default aggregation scope.

    Args:
        targets: List of target IDs to track. Empty list = all targets.

    Returns:
        Dict with 'tracked' and 'connected' lists.

    Raises:
        RPCError: If any target in list is not connected.
    """
    # Validate all targets exist in connections
    invalid = [t for t in targets if t not in ctx.service.connections]
    if invalid:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Unknown targets: {invalid}")

    ctx.service.set_tracked_targets(targets)
    return {
        "tracked": ctx.service.tracked_targets,
        "connected": list(ctx.service.connections.keys()),
    }


def targets_clear(ctx: RPCContext) -> dict:
    """Clear tracked targets (show all).

    Returns:
        Dict with 'tracked' and 'connected' lists.
    """
    ctx.service.set_tracked_targets([])
    return {
        "tracked": ctx.service.tracked_targets,
        "connected": list(ctx.service.connections.keys()),
    }


def targets_get(ctx: RPCContext) -> dict:
    """Get current tracked targets.

    Returns:
        Dict with 'tracked' and 'connected' lists.
    """
    return {
        "tracked": ctx.service.tracked_targets,
        "connected": list(ctx.service.connections.keys()),
    }


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
    try:
        return ctx.service.register_port(port)
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))


def ports_remove(ctx: RPCContext, port: int) -> dict:
    """Unregister a port from daemon tracking.

    Args:
        port: Chrome debug port number to unregister

    Returns:
        Dict with 'port' and 'removed' boolean

    Raises:
        RPCError: If port is protected or not found
    """
    try:
        return ctx.service.unregister_port(port)
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))


def ports_list(ctx: RPCContext) -> dict:
    """List all registered ports with their status.

    Returns:
        Dict with 'ports' list. Each port includes:
        - port: Port number
        - page_count: Number of pages on this port
        - connection_count: Number of active connections
        - status: 'active' if pages available, 'reachable' otherwise
    """
    return ctx.service.list_ports()
