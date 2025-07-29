"""Init command for orchestrating development environments.

Leverages bash command for execution - no duplication of logic.
"""

from typing import Any

from ..app import app
from ..config import get_config_manager
from ..tmux import (
    new_session,
    list_sessions,
    create_panes_with_layout,
    kill_session,
)
from ..types import ServiceConfig
from .bash import bash
from replkit2.textkit.icons import ICONS
from ..errors import markdown_error_response, table_error_response, string_error_response


def _sort_by_dependencies(services: list[ServiceConfig]) -> list[ServiceConfig]:
    """Simple topological sort for service dependencies."""
    sorted_services = []
    remaining = services.copy()

    while remaining:
        # Find services with no unmet dependencies
        ready = []
        for service in remaining:
            if not service.depends_on:
                ready.append(service)
            else:
                # Check if all dependencies are already sorted
                deps_met = all(any(s.name == dep for s in sorted_services) for dep in service.depends_on)
                if deps_met:
                    ready.append(service)

        if not ready:
            # Circular dependency
            names = [s.name for s in remaining]
            raise ValueError(f"Circular dependency detected among: {', '.join(names)}")

        # Add ready services to sorted list
        for service in ready:
            sorted_services.append(service)
            remaining.remove(service)

    return sorted_services


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": "Initialize development environment from config"},
)
def init(state, group: str) -> dict[str, Any]:
    """Initialize a development environment from configuration.

    Creates a tmux session with multiple panes and starts services
    using the bash command for execution.
    """
    try:
        config_manager = get_config_manager()
    except Exception as e:
        return markdown_error_response(f"Failed to load configuration: {e}")

    # Get init group
    try:
        init_group = config_manager.get_init_group(group)
        if not init_group:
            available = config_manager.list_init_groups()
            message = f"Init group '{group}' not found.\nAvailable groups: {', '.join(available) or 'none'}"
            return markdown_error_response(message)
    except Exception as e:
        return markdown_error_response(f"Failed to get init group: {e}")

    # Check if session already exists
    try:
        existing = [s.name for s in list_sessions()]
        if init_group.name in existing:
            message = f"Session '{init_group.name}' already exists.\nUse kill('{init_group.name}') to remove it."
            return markdown_error_response(message)
    except Exception as e:
        return markdown_error_response(f"Failed to list sessions: {e}")

    elements = []
    elements.append({"type": "heading", "content": f"Initializing {group}", "level": 2})

    # Create session
    try:
        pane_id, swp = new_session(init_group.name)
        elements.append({"type": "text", "content": f"{ICONS['success']} Created session '{init_group.name}'"})
    except Exception as e:
        return markdown_error_response(f"Failed to create session: {e}")

    # Create additional panes if needed
    max_pane = max((s.pane for s in init_group.services), default=0)
    num_panes = max_pane + 1

    if num_panes > 1:
        try:
            create_panes_with_layout(init_group.name, num_panes, init_group.layout)
            elements.append(
                {
                    "type": "text",
                    "content": f"{ICONS['success']} Created {num_panes} panes with {init_group.layout} layout",
                }
            )
        except Exception as e:
            # Clean up the session we just created
            try:
                kill_session(init_group.name)
            except Exception:
                pass
            return markdown_error_response(f"Failed to create panes: {e}")

    # Sort services by dependencies
    try:
        sorted_services = _sort_by_dependencies(init_group.services)
    except ValueError as e:
        # Clean up the session
        try:
            kill_session(init_group.name)
        except Exception:
            pass
        return markdown_error_response(str(e))

    # Start services
    elements.append({"type": "heading", "content": "Starting services", "level": 3})

    failed = False
    for service in sorted_services:
        # Use bash to execute the command
        # bash already handles ready patterns, timeouts, and process detection
        result = bash(
            state,
            command=service.command,
            target=service.full_name,  # e.g., "demo.backend"
            wait=bool(service.ready_pattern),  # Wait if we have a ready pattern
            timeout=service.timeout,
        )

        # Extract status from result
        status = result.get("frontmatter", {}).get("status", "unknown")

        if status == "ready":
            elements.append({"type": "text", "content": f"{ICONS['success']} {service.name} ready"})
        elif status == "completed":
            elements.append({"type": "text", "content": f"{ICONS['success']} {service.name} started"})
        elif status == "running":
            elements.append({"type": "text", "content": f"{ICONS['info']} {service.name} running (no wait)"})
        else:
            # Error or timeout
            elements.append({"type": "text", "content": f"{ICONS['error']} {service.name} failed ({status})"})
            failed = True
            break

    # Summary
    elements.append({"type": "heading", "content": "Summary", "level": 3})

    if not failed:
        service_list = []
        for service in init_group.services:
            service_list.append(
                f"{ICONS['arrow']}`{service.full_name}` {ICONS['arrow']} `{service.session_window_pane}`"
            )

        elements.extend(
            [
                {"type": "list", "items": service_list, "ordered": False},
                {"type": "text", "content": ""},
                {"type": "text", "content": "Use service names to target specific panes:"},
                {"type": "code_block", "content": f'bash("ps aux", "{group}.backend")', "language": "python"},
            ]
        )

        status = "success"
    else:
        elements.append({"type": "text", "content": "Initialization failed. Some services may have started."})
        elements.append({"type": "text", "content": f"Run `kill('{init_group.name}')` to clean up."})
        status = "error"

    return {
        "elements": elements,
        "frontmatter": {
            "status": status,
            "group": group,
            "session": init_group.name,
            "services": len(init_group.services),
        },
    }


@app.command(
    display="table",
    headers=["Group", "Services", "Layout"],
    fastmcp={"type": "tool", "description": "List available init groups"},
)
def init_list(state) -> list[dict]:
    """List available init groups from configuration."""
    try:
        config_manager = get_config_manager()
    except Exception as e:
        return table_error_response(f"Failed to load configuration: {e}")

    rows = []
    for group_name in config_manager.list_init_groups():
        group = config_manager.get_init_group(group_name)
        if group:
            rows.append({"Group": group_name, "Services": len(group.services), "Layout": group.layout})

    return rows


# Helper to kill sessions (commonly needed after init)
@app.command(
    display="text",
    fastmcp={"type": "tool", "description": "Kill a tmux session"},
)
def kill(state, session: str) -> str:
    """Kill a tmux session."""
    try:
        if kill_session(session):
            return f"Killed session '{session}'"
        else:
            return string_error_response(f"Session '{session}' not found")
    except Exception as e:
        return string_error_response(f"Failed to kill session: {e}")
