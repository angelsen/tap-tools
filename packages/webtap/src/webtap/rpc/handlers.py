"""RPC method handlers - thin wrappers around WebTapService.

This module contains all RPC method implementations. Handlers receive RPCContext
and delegate to WebTapService for business logic. State transitions are managed
by the ConnectionMachine via ctx.machine.

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

# Common state requirements
CONNECTED_STATES = ["connected", "inspecting"]
CONNECTED_ONLY = ["connected"]


__all__ = ["register_handlers", "CONNECTED_STATES", "CONNECTED_ONLY"]


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


def connect(ctx: RPCContext, page_id: str | None = None, page: int | None = None) -> dict:
    """Connect to a Chrome page by index or page ID.

    Args:
        page_id: Chrome page ID. Defaults to None.
        page: Page index. Defaults to None.

    Returns:
        Connection result with page details.

    Raises:
        RPCError: If connection fails or invalid parameters.
    """
    if page is not None and page_id is not None:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Cannot specify both 'page' and 'page_id'")
    if page is None and page_id is None:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Must specify 'page' or 'page_id'")

    if ctx.service.cdp.is_connected:
        current_info = ctx.service.cdp.page_info or {}
        current_id = current_info.get("id")
        if page_id and page_id == current_id:
            return {
                "connected": True,
                "already_connected": True,
                "title": current_info.get("title", ""),
                "url": current_info.get("url", ""),
            }

    ctx.machine.start_connect()

    try:
        result = ctx.service.connect_to_page(page_index=page, page_id=page_id)
        ctx.machine.connect_success()
        return {"connected": True, **result}

    except Exception as e:
        ctx.machine.connect_failed()
        raise RPCError(ErrorCode.NOT_CONNECTED, str(e))


def disconnect(ctx: RPCContext) -> dict:
    """Disconnect from currently connected page."""
    ctx.machine.start_disconnect()

    try:
        ctx.service.disconnect()
        ctx.machine.disconnect_complete()
        return {"disconnected": True}

    except Exception as e:
        # Still complete the transition even if there's an error
        ctx.machine.disconnect_complete()
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def pages(ctx: RPCContext) -> dict:
    """Get available Chrome pages from /json endpoint."""
    try:
        pages_data = ctx.service.cdp.list_pages()
        return {"pages": pages_data}
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


def navigate(ctx: RPCContext, url: str) -> dict:
    """Navigate to URL.

    Args:
        url: Target URL
    """
    try:
        result = ctx.service.cdp.execute("Page.navigate", {"url": url})
        return {
            "url": url,
            "frame_id": result.get("frameId"),
            "loader_id": result.get("loaderId"),
            "error": result.get("errorText"),
        }
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Navigation failed: {e}")


def reload(ctx: RPCContext, ignore_cache: bool = False) -> dict:
    """Reload current page.

    Args:
        ignore_cache: Ignore browser cache. Defaults to False.
    """
    try:
        ctx.service.cdp.execute("Page.reload", {"ignoreCache": ignore_cache})
        return {"reloaded": True, "ignore_cache": ignore_cache}
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Reload failed: {e}")


def back(ctx: RPCContext) -> dict:
    """Navigate back in history."""
    try:
        return _navigate_history(ctx, -1)
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Back navigation failed: {e}")


def forward(ctx: RPCContext) -> dict:
    """Navigate forward in history."""
    try:
        return _navigate_history(ctx, +1)
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Forward navigation failed: {e}")


def _navigate_history(ctx: RPCContext, direction: int) -> dict:
    """Navigate history by direction.

    Args:
        direction: -1 for back, +1 for forward
    """
    result = ctx.service.cdp.execute("Page.getNavigationHistory", {})
    entries = result.get("entries", [])
    current = result.get("currentIndex", 0)
    target_idx = current + direction

    if target_idx < 0:
        return {"navigated": False, "reason": "Already at first entry"}
    if target_idx >= len(entries):
        return {"navigated": False, "reason": "Already at last entry"}

    target = entries[target_idx]
    ctx.service.cdp.execute("Page.navigateToHistoryEntry", {"entryId": target["id"]})

    return {
        "navigated": True,
        "title": target.get("title", ""),
        "url": target.get("url", ""),
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
) -> dict:
    """Execute JavaScript in browser context.

    Args:
        code: JavaScript code to execute
        selection: Browser selection number to bind to 'element' variable. Defaults to None.
        persist: Keep variables in global scope. Defaults to False.
        await_promise: Await promise results. Defaults to False.
        return_value: Return the result value. Defaults to True.
    """
    try:
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

        result = ctx.service.cdp.execute(
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
