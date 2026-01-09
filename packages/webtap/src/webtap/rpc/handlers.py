"""RPC method handlers - thin wrappers around WebTapService.

PUBLIC API:
  - register_handlers: Register all RPC handlers with the framework

Handlers receive RPCContext and delegate to WebTapService for business logic.
Per-target state is managed by ConnectionManager via ctx.service.conn_mgr.
"""

from webtap.rpc.errors import ErrorCode, RPCError
from webtap.rpc.framework import RPCContext, RPCFramework

_CONNECTED_STATES = ["connected", "inspecting"]
_CONNECTED_ONLY = ["connected"]

__all__ = ["register_handlers"]


def _get_connected_targets(ctx: RPCContext) -> list[dict]:
    """Get minimal target info for response embedding."""
    return [
        {
            "target": conn.target,
            "title": conn.page_info.get("title", ""),
            "url": conn.page_info.get("url", ""),
        }
        for conn in ctx.service.conn_mgr.get_all()
    ]


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
    rpc.method("connect")(_connect)
    rpc.method("disconnect", requires_state=_CONNECTED_STATES)(_disconnect)
    rpc.method("pages", broadcasts=False)(_pages)
    rpc.method("status", broadcasts=False)(_status)
    rpc.method("clear", requires_state=_CONNECTED_STATES)(_clear)

    rpc.method("browser.startInspect", requires_state=_CONNECTED_ONLY)(_browser_start_inspect)
    rpc.method("browser.stopInspect", requires_state=_CONNECTED_STATES)(_browser_stop_inspect)
    rpc.method("browser.clear", requires_state=_CONNECTED_STATES)(_browser_clear)

    rpc.method("fetch")(_fetch)

    rpc.method("network", requires_state=_CONNECTED_STATES, broadcasts=False)(_network)
    rpc.method("request", requires_state=_CONNECTED_STATES, broadcasts=False)(_request)
    rpc.method("console", requires_state=_CONNECTED_STATES, broadcasts=False)(_console)
    rpc.method("entry", requires_state=_CONNECTED_STATES, broadcasts=False)(_entry)

    rpc.method("filters.status", broadcasts=False)(_filters_status)
    rpc.method("filters.add", broadcasts=False)(_filters_add)
    rpc.method("filters.remove", broadcasts=False)(_filters_remove)
    rpc.method("filters.enable", requires_state=_CONNECTED_STATES)(_filters_enable)
    rpc.method("filters.disable", requires_state=_CONNECTED_STATES)(_filters_disable)
    rpc.method("filters.enableAll", requires_state=_CONNECTED_STATES)(_filters_enable_all)
    rpc.method("filters.disableAll", requires_state=_CONNECTED_STATES)(_filters_disable_all)

    rpc.method("navigate", requires_state=_CONNECTED_STATES)(_navigate)
    rpc.method("reload", requires_state=_CONNECTED_STATES)(_reload)
    rpc.method("back", requires_state=_CONNECTED_STATES)(_back)
    rpc.method("forward", requires_state=_CONNECTED_STATES)(_forward)
    rpc.method("history", requires_state=_CONNECTED_STATES, broadcasts=False)(_history)
    rpc.method("page", requires_state=_CONNECTED_STATES, broadcasts=False)(_page)

    rpc.method("js")(_js)

    rpc.method("cdp", requires_state=_CONNECTED_STATES)(_cdp)
    rpc.method("errors.dismiss")(_errors_dismiss)

    rpc.method("targets.set")(_targets_set)
    rpc.method("targets.clear")(_targets_clear)
    rpc.method("targets.get", broadcasts=False)(_targets_get)

    rpc.method("ports.add", broadcasts=False)(_ports_add)
    rpc.method("ports.remove", broadcasts=False)(_ports_remove)
    rpc.method("ports.list", broadcasts=False)(_ports_list)


def _connect(ctx: RPCContext, target: str) -> dict:
    """Connect to a Chrome page by target ID."""
    try:
        result = ctx.service.connect_to_page(target=target)
        return {"connected": True, **result}
    except Exception as e:
        raise RPCError(ErrorCode.NOT_CONNECTED, str(e))


def _disconnect(ctx: RPCContext, target: str | None = None) -> dict:
    """Disconnect from target(s)."""
    try:
        if target:
            ctx.service.disconnect_target(target)
            disconnected = [target]
        else:
            disconnected = list(ctx.service.connections.keys())
            ctx.service.disconnect()

        return {"disconnected": disconnected}

    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def _pages(ctx: RPCContext) -> dict:
    """Get available Chrome pages from all tracked ports."""
    try:
        return ctx.service.list_pages()
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Failed to list pages: {e}")


def _status(ctx: RPCContext) -> dict:
    """Get comprehensive status including connection, events, browser, and fetch details."""
    from webtap.api import get_full_state

    return get_full_state()


def _clear(ctx: RPCContext, events: bool = True, console: bool = False) -> dict:
    """Clear various data stores."""
    cleared = []

    if events:
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


def _browser_start_inspect(ctx: RPCContext, target: str) -> dict:
    """Enable CDP element inspection mode on a specific target."""
    if target not in ctx.service.connections:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Target '{target}' not connected")

    ctx.service.conn_mgr.set_inspecting(target, True)
    result = ctx.service.dom.start_inspect(target)
    return {**result}


def _browser_stop_inspect(ctx: RPCContext) -> dict:
    """Disable CDP element inspection mode."""
    for target in ctx.service.connections:
        ctx.service.conn_mgr.set_inspecting(target, False)
    result = ctx.service.dom.stop_inspect()
    return {**result}


def _browser_clear(ctx: RPCContext) -> dict:
    """Clear all element selections."""
    ctx.service.dom.clear_selections()
    return {"success": True, "selections": {}}


def _fetch(ctx: RPCContext, rules: dict | None = None) -> dict:
    """Handle fetch configuration.

    API:
        fetch()                              -> get status
        fetch({"capture": False})            -> disable capture globally
        fetch({"capture": True})             -> re-enable capture globally
        fetch({"block": [...], "target": "..."}) -> set block rules for target
        fetch({"mock": {...}, "target": "..."})  -> set mock rules for target
        fetch({"target": "..."})             -> clear rules for target
    """
    if rules is None:
        # No args - return status
        return ctx.service.fetch.get_status()

    # Check for global capture toggle
    if "capture" in rules and len(rules) == 1:
        return ctx.service.fetch.set_capture(rules["capture"])

    # Check for target-specific rules
    if "target" in rules:
        target = rules["target"]
        if target not in ctx.service.connections:
            raise RPCError(ErrorCode.INVALID_PARAMS, f"Target '{target}' not connected")
        return ctx.service.fetch.set_rules(
            target=target,
            block=rules.get("block"),
            mock=rules.get("mock"),
        )

    # Block/mock without target is error
    if "block" in rules or "mock" in rules:
        raise RPCError(ErrorCode.INVALID_PARAMS, "block/mock rules require 'target' parameter")

    return ctx.service.fetch.get_status()


def _network(
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
    """Query network requests with inline filters."""
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
    return {"targets": _get_connected_targets(ctx), "requests": requests}


def _request(ctx: RPCContext, id: int, target: str | None = None, fields: list[str] | None = None) -> dict:
    """Get request details with field selection."""
    entry = ctx.service.network.get_request_details(id, target=target)
    if not entry:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Request {id} not found")

    selected = ctx.service.network.select_fields(entry, fields)
    return {"entry": selected}


def _console(ctx: RPCContext, limit: int = 50, level: str | None = None, target: str | list[str] | None = None) -> dict:
    """Get console messages."""
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

    return {"targets": _get_connected_targets(ctx), "messages": messages}


def _entry(ctx: RPCContext, id: int, fields: list[str] | None = None) -> dict:
    """Get console entry details with field selection."""
    entry_data = ctx.service.console.get_entry_details(id)
    if not entry_data:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Console entry {id} not found")

    selected = ctx.service.console.select_fields(entry_data, fields)
    return {"entry": selected}


def _filters_status(ctx: RPCContext) -> dict:
    """Get all filter groups with enabled status."""
    return ctx.service.filters.get_status()


def _filters_add(ctx: RPCContext, name: str, hide: dict) -> dict:
    """Add a new filter group."""
    ctx.service.filters.add(name, hide)
    return {"added": True, "name": name}


def _filters_remove(ctx: RPCContext, name: str) -> dict:
    """Remove a filter group."""
    result = ctx.service.filters.remove(name)
    if result:
        return {"removed": True, "name": name}
    return {"removed": False, "name": name}


def _filters_enable(ctx: RPCContext, name: str) -> dict:
    """Enable a filter group."""
    result = ctx.service.filters.enable(name)
    if result:
        return {"enabled": True, "name": name}
    raise RPCError(ErrorCode.INVALID_PARAMS, f"Group '{name}' not found")


def _filters_disable(ctx: RPCContext, name: str) -> dict:
    """Disable a filter group."""
    result = ctx.service.filters.disable(name)
    if result:
        return {"disabled": True, "name": name}
    raise RPCError(ErrorCode.INVALID_PARAMS, f"Group '{name}' not found")


def _filters_enable_all(ctx: RPCContext) -> dict:
    """Enable all filter groups."""
    fm = ctx.service.filters
    for name in fm.groups:
        fm.enable(name)
    return {"enabled": list(fm.enabled)}


def _filters_disable_all(ctx: RPCContext) -> dict:
    """Disable all filter groups."""
    ctx.service.filters.disable_all()
    return {"enabled": []}


def _cdp(ctx: RPCContext, command: str, params: dict | None = None, target: str | None = None) -> dict:
    """Execute arbitrary CDP command."""
    try:
        cdp_session = _resolve_cdp_session(ctx, target)
        result = cdp_session.execute(command, params or {})
        return {"result": result}
    except RPCError:
        raise
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, str(e))


def _errors_dismiss(ctx: RPCContext) -> dict:
    """Dismiss the current error."""
    ctx.service.clear_error()
    return {"success": True}


def _navigate(ctx: RPCContext, url: str, target: str) -> dict:
    """Navigate to URL."""
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


def _reload(ctx: RPCContext, target: str, ignore_cache: bool = False) -> dict:
    """Reload current page."""
    try:
        ctx.service.execute_on_target(target, lambda cdp: cdp.execute("Page.reload", {"ignoreCache": ignore_cache}))
        return {"reloaded": True, "ignore_cache": ignore_cache}
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Reload failed: {e}")


def _back(ctx: RPCContext, target: str) -> dict:
    """Navigate back in history."""
    try:
        return ctx.service.execute_on_target(target, lambda cdp: _navigate_history_impl(cdp, -1))
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Back navigation failed: {e}")


def _forward(ctx: RPCContext, target: str) -> dict:
    """Navigate forward in history."""
    try:
        return ctx.service.execute_on_target(target, lambda cdp: _navigate_history_impl(cdp, +1))
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        raise RPCError(ErrorCode.INTERNAL_ERROR, f"Forward navigation failed: {e}")


def _navigate_history_impl(cdp, direction: int) -> dict:
    """Navigate to history entry by direction offset."""
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


def _history(ctx: RPCContext, target: str | None = None) -> dict:
    """Get navigation history."""
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


def _page(ctx: RPCContext, target: str | None = None) -> dict:
    """Get current page info with title from DOM."""
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


def _js(
    ctx: RPCContext,
    code: str,
    target: str,
    selection: int | None = None,
    persist: bool = False,
    await_promise: bool = False,
    return_value: bool = True,
) -> dict:
    """Execute JavaScript in browser context."""
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
    """Execute JavaScript on a CDP session with optional element binding."""
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


def _targets_set(ctx: RPCContext, targets: list[str]) -> dict:
    """Set tracked targets for default aggregation scope."""
    # Validate all targets exist in connections
    invalid = [t for t in targets if t not in ctx.service.connections]
    if invalid:
        raise RPCError(ErrorCode.INVALID_PARAMS, f"Unknown targets: {invalid}")

    ctx.service.set_tracked_targets(targets)
    return {
        "tracked": ctx.service.tracked_targets,
        "connected": list(ctx.service.connections.keys()),
    }


def _targets_clear(ctx: RPCContext) -> dict:
    """Clear tracked targets (show all)."""
    ctx.service.set_tracked_targets([])
    return {
        "tracked": ctx.service.tracked_targets,
        "connected": list(ctx.service.connections.keys()),
    }


def _targets_get(ctx: RPCContext) -> dict:
    """Get current tracked targets."""
    return {
        "tracked": ctx.service.tracked_targets,
        "connected": list(ctx.service.connections.keys()),
    }


def _ports_add(ctx: RPCContext, port: int) -> dict:
    """Register a Chrome debug port with the daemon."""
    try:
        return ctx.service.register_port(port)
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))


def _ports_remove(ctx: RPCContext, port: int) -> dict:
    """Unregister a port from daemon tracking."""
    try:
        return ctx.service.unregister_port(port)
    except ValueError as e:
        raise RPCError(ErrorCode.INVALID_PARAMS, str(e))


def _ports_list(ctx: RPCContext) -> dict:
    """List all registered ports with their status."""
    return ctx.service.list_ports()
