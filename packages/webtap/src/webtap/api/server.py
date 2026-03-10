"""Daemon server lifecycle management.

PUBLIC API:
  - run_daemon_server: Run daemon server in foreground (blocking)
"""

import asyncio
import logging
from typing import Any

import uvicorn
from fastapi.responses import PlainTextResponse

from webtap.api.app import api
from webtap.api.sse import broadcast_processor, get_broadcast_queue, set_broadcast_ready_event, router as sse_router
from webtap.services.daemon_state import DaemonState
from webtap.rpc import RPCFramework
from webtap.rpc.handlers import register_handlers

__all__ = ["run_daemon_server"]

logger = logging.getLogger(__name__)


def _format_controls(target: str, title: str, controls: dict) -> str:
    """Format a target's controls as plain text for LLM context.

    Args:
        target: Target ID (e.g., "9222:abc123")
        title: Page title
        controls: Output of window.controls.describeAll()

    Returns:
        Formatted text section for this target
    """
    lines = [f"  [{target} — {title}]"]
    for name, desc in controls.items():
        state = desc.get("state", "")
        lines.append(f"    {name} — {state}")
        for action_name, action in desc.get("actions", {}).items():
            action_desc = action.get("description", "")
            params = action.get("params", {})
            param_names = list(params.get("properties", {}).keys()) if isinstance(params, dict) else []
            args_str = ", ".join(param_names)
            js_call = f"controls.invoke('{name}', '{action_name}'"
            if args_str:
                js_call += ", {" + ", ".join(f"{p}: ..." for p in param_names) + "}"
            js_call += ")"
            lines.append(f'      js("{js_call}", "{target}")  {action_desc}')
        for prop_name, prop in desc.get("properties", {}).items():
            prop_desc = prop.get("description", "")
            value = prop.get("value")
            val_str = f" → {value}" if value is not None else ""
            lines.append(f"      {name}.{prop_name}{val_str}  {prop_desc}")
    lines.append("")
    return "\n".join(lines)


_console_watermark: float = 0.0

_MAX_UNIQUE_MESSAGES = 5


def _dedup_messages(msgs: list[tuple]) -> list[tuple[str, str, int]]:
    """Deduplicate messages by content, preserving order of first occurrence.

    Args:
        msgs: Row tuples (rowid, level, source, message, timestamp, target)

    Returns:
        List of (level, message, count) tuples, ordered by first occurrence
    """
    from collections import Counter

    # Count by (level, message)
    counts: Counter[tuple[str, str]] = Counter()
    order: list[tuple[str, str]] = []
    for m in msgs:
        level = m[1] or "log"
        message = m[3] or ""
        if len(message) > 200:
            message = message[:200] + "..."
        key = (level, message)
        if key not in counts:
            order.append(key)
        counts[key] += 1

    return [(level, message, counts[(level, message)]) for level, message in order]


def _format_deduped(entries: list[tuple[str, str, int]], indent: str = "    ") -> list[str]:
    """Format deduped entries as lines with optional (xN) counts."""
    lines = []
    for level, message, count in entries:
        suffix = f" (x{count})" if count > 1 else ""
        lines.append(f"{indent}[{level}]{suffix} {message}")
    return lines


def _build_console_section(service: Any, targets: list[str]) -> str:
    """Build console messages section for /prompt, with drain and dedup.

    Returns only messages newer than the watermark. Deduplicates repeated
    messages and caps at 5 unique entries. Advances watermark after building.
    """
    global _console_watermark
    from collections import defaultdict

    all_msgs = service.console.get_recent_messages(targets=targets, limit=100)
    if not all_msgs:
        return ""

    # Drain: filter to messages newer than watermark
    # Row tuple: (rowid, level, source, message, timestamp, target)
    new_msgs = [m for m in all_msgs if m[4] and float(m[4]) > _console_watermark]
    if not new_msgs:
        return ""

    # Advance watermark
    max_ts = max(float(m[4]) for m in new_msgs if m[4])
    _console_watermark = max_ts

    # Partition: errors/warnings vs others
    errors_warnings = [m for m in new_msgs if m[1] in ("error", "warning")]
    others = [m for m in new_msgs if m[1] not in ("error", "warning")]

    # Dedup each partition
    deduped_errors = _dedup_messages(errors_warnings)
    deduped_others = _dedup_messages(others)

    # Cap each
    shown_errors = deduped_errors[:_MAX_UNIQUE_MESSAGES]
    shown_others = deduped_others[:_MAX_UNIQUE_MESSAGES]
    total_shown = shown_errors + shown_others

    if not total_shown:
        return ""

    # Count totals (pre-dedup)
    error_count = len(errors_warnings)
    warning_count = sum(1 for m in new_msgs if m[1] == "warning")
    total_raw = len(new_msgs)

    # Build header
    parts = [f"Console ({total_raw} message{'s' if total_raw != 1 else ''}"]
    if error_count:
        parts.append(f", {error_count} error{'s' if error_count != 1 else ''}")
    if warning_count:
        parts.append(f", {warning_count} warning{'s' if warning_count != 1 else ''}")
    header = "".join(parts) + "):"

    lines = [header]

    # Group by target for display
    by_target: dict[str, list] = defaultdict(list)
    for m in new_msgs:
        by_target[m[5]].append(m)

    for tid in by_target:
        conn = service.connections.get(tid)
        title = conn.page_info.get("title", tid) if conn else tid
        lines.append(f"  [{tid} — {title}]")

    # Deduped entries (flat, not per-target — keeps it compact)
    lines.extend(_format_deduped(total_shown))

    hidden = (len(deduped_errors) - len(shown_errors)) + (len(deduped_others) - len(shown_others))
    if hidden > 0:
        lines.append(f"    ... {hidden} more unique messages")
    lines.append("  Use console() for full details.")

    return "\n".join(lines)


def _check_console_errors(service: Any, targets: list[str]) -> dict | None:
    """Check for new console errors/warnings since watermark.

    Returns Stop hook block decision if errors found, None otherwise.
    Deduplicates and caps at 5 unique errors. Advances watermark.
    """
    global _console_watermark

    all_msgs = service.console.get_recent_messages(targets=targets, limit=100)
    if not all_msgs:
        return None

    # Drain: only messages newer than watermark
    new_msgs = [m for m in all_msgs if m[4] and float(m[4]) > _console_watermark]
    if not new_msgs:
        return None

    # Advance watermark for ALL new messages
    max_ts = max(float(m[4]) for m in new_msgs if m[4])
    _console_watermark = max_ts

    # Filter for errors/warnings only
    errors_warnings = [m for m in new_msgs if m[1] in ("error", "warning")]
    if not errors_warnings:
        return None

    # Dedup and cap
    deduped = _dedup_messages(errors_warnings)
    shown = deduped[:_MAX_UNIQUE_MESSAGES]

    reason_lines = ["New console errors detected:"]
    reason_lines.extend(_format_deduped(shown, indent="  "))

    hidden = len(deduped) - len(shown)
    if hidden > 0:
        reason_lines.append(f"  ... {hidden} more unique errors")
    reason_lines.append("Use console() for full details.")

    return {"decision": "block", "reason": "\n".join(reason_lines)}


def run_daemon_server(host: str = "127.0.0.1", port: int = 37650):
    """Run daemon server in foreground (blocking).

    This function is called by daemon.py when running in --daemon mode.
    It initializes daemon state with CDPSession and WebTapService,
    then runs the API server.

    Args:
        host: Host to bind to
        port: Port to bind to
    """
    import os
    import webtap.api.app as app_module
    from fastapi import Request

    # Initialize daemon state
    app_module.app_state = DaemonState()
    logger.info("Daemon initialized with CDPSession and WebTapService")

    # Initialize RPC framework and register handlers
    rpc = RPCFramework(app_module.app_state.service)
    register_handlers(rpc)
    app_module.app_state.service.rpc = rpc
    logger.info("RPC framework initialized with 22 handlers")

    @api.post("/rpc")
    async def handle_rpc(request: Request) -> dict:
        """Handle JSON-RPC 2.0 requests.

        Args:
            request: FastAPI request object with JSON body

        Returns:
            JSON-RPC response dictionary
        """
        body = await request.json()
        headers = dict(request.headers)
        return await rpc.handle(body, headers=headers)

    @api.get("/health")
    async def health_check() -> dict:
        """Health check endpoint for extension.

        Returns:
            Dictionary with status, pid, and version
        """
        from webtap import __version__

        return {"status": "ok", "pid": os.getpid(), "version": __version__}

    @api.get("/prompt", response_class=PlainTextResponse)
    async def get_prompt() -> str:
        """Aggregate controls and console messages from watched targets.

        Returns controls state and drained console messages as plain text
        for LLM context injection via UserPromptSubmit hook.
        """
        if not app_module.app_state:
            return ""

        service = app_module.app_state.service
        targets = service.get_tracked_or_all()
        if not targets:
            return ""

        # Controls section
        control_sections: list[str] = []
        for tid in targets:
            conn = service.connections.get(tid)
            if not conn:
                continue
            try:
                result = conn.cdp.execute(
                    "Runtime.evaluate",
                    {
                        "expression": "window.controls?.describeAll()",
                        "returnByValue": True,
                        "awaitPromise": False,
                    },
                    timeout=2.0,
                )
                value = result.get("result", {}).get("value")
                if not value:
                    continue
                title = conn.page_info.get("title", tid)
                control_sections.append(_format_controls(tid, title, value))
            except Exception:
                continue

        # Console section (drained)
        console_section = _build_console_section(service, targets)

        # Build output
        parts: list[str] = []

        if control_sections:
            count = len(control_sections)
            parts.append(f"Active controls ({count} target{'s' if count != 1 else ''}):")
            parts.append("")
            parts.extend(control_sections)
            parts.append("Tip: Actions emit observations to console. Use console() to verify results.")

        if console_section:
            if parts:
                parts.append("")
            parts.append(console_section)

        if not parts:
            return ""

        return "\n".join(parts)

    @api.get("/console-check")
    async def console_check() -> dict | str:
        """Check for new console errors since last prompt.

        Used by Stop hook to detect errors caused during Claude's turn.
        Returns block decision if new errors/warnings found.
        """
        if not app_module.app_state:
            return ""

        service = app_module.app_state.service
        targets = service.get_tracked_or_all()
        if not targets:
            return ""

        result = _check_console_errors(service, targets)
        if result:
            return result
        return ""

    # Include SSE endpoint
    api.include_router(sse_router)

    async def _run():
        """Run server with proper shutdown handling."""
        config = uvicorn.Config(
            api,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # Create event for broadcast processor ready signal
        ready_event = asyncio.Event()
        set_broadcast_ready_event(ready_event)

        # Start broadcast processor in background
        broadcast_task = asyncio.create_task(broadcast_processor())

        # Wait for processor to be ready (with timeout)
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("Broadcast processor failed to start")
            broadcast_task.cancel()
            return

        # Wire broadcast queue to service
        queue = get_broadcast_queue()
        if queue and app_module.app_state:
            app_module.app_state.service.set_broadcast_queue(queue)
            logger.debug("Broadcast queue wired to WebTapService")

        # Start background services (Chrome watcher)
        if app_module.app_state:
            app_module.app_state.service.start()

        try:
            await server.serve()
        except (SystemExit, KeyboardInterrupt):
            pass
        finally:
            if not broadcast_task.done():
                broadcast_task.cancel()
                try:
                    await broadcast_task
                except asyncio.CancelledError:
                    pass

    try:
        asyncio.run(_run())
    except (SystemExit, KeyboardInterrupt):
        pass
    except Exception as e:
        logger.error(f"Daemon server failed: {e}")
    finally:
        if app_module.app_state:
            app_module.app_state.cleanup()
        logger.info("Daemon cleanup complete")
