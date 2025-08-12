"""Run command - orchestrate development environments using pane-centric architecture.

Fresh implementation that fully embraces the pane paradigm.
No backwards compatibility - clean, modern approach.

PUBLIC API:
  - run: Run development environment from configuration
  - run_list: List available run configurations
  - kill: Stop running environment
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
import os

from ..app import app
from ..config import get_config_manager
from ..pane import Pane, send_command
from ..tmux.session import session_exists, create_session, kill_session
from ..tmux.pane import create_panes_with_layout


@dataclass
class _ServiceBuilder:
    """Builder for validated service configuration."""

    name: str
    group: str
    pane_index: int
    command: str
    path: Optional[Path] = None
    env: dict[str, str] = field(default_factory=dict)
    ready_pattern: Optional[str] = None
    timeout: float = 30.0
    depends_on: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Get full service name (group.name)."""
        return f"{self.group}.{self.name}"

    @property
    def target(self) -> str:
        """Get target for this service (group:0.pane_index)."""
        return f"{self.group}:0.{self.pane_index}"

    def validate(self, config_dir: Path) -> list[str]:
        """Validate service configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if self.path:
            full_path = config_dir / self.path if not self.path.is_absolute() else self.path
            if not full_path.exists():
                errors.append(f"Path does not exist: {full_path}")
            elif not full_path.is_dir():
                errors.append(f"Path is not a directory: {full_path}")

        for key, value in self.env.items():
            if value.startswith("$"):
                env_var = value[1:]
                if env_var not in os.environ:
                    errors.append(f"Environment variable not set: {env_var}")

        return errors

    def build_command(self, config_dir: Path) -> str:
        """Build the full command with cd and environment setup.

        Args:
            config_dir: Directory containing the config file

        Returns:
            Full command string ready for execution
        """
        parts = []

        for key, value in self.env.items():
            if value.startswith("$"):
                actual_value = os.environ.get(value[1:], "")
            else:
                actual_value = value
            parts.append(f"export {key}={actual_value}")

        if self.path:
            full_path = config_dir / self.path if not self.path.is_absolute() else self.path
            parts.append(f"cd {full_path}")

        parts.append(self.command)

        return " && ".join(parts) if len(parts) > 1 else self.command


def _parse_service_config(service_name: str, service_data: dict, group_name: str, pane_index: int) -> _ServiceBuilder:
    """Parse service configuration into builder.

    Args:
        service_name: Name of the service
        service_data: Raw config data for the service
        group_name: Name of the group this service belongs to
        pane_index: Pane index for this service
    """
    return _ServiceBuilder(
        name=service_name,
        group=group_name,
        pane_index=service_data.get("pane", pane_index),
        command=service_data["command"],
        path=Path(service_data["path"]) if "path" in service_data else None,
        env=service_data.get("env", {}),
        ready_pattern=service_data.get("ready_pattern"),
        timeout=service_data.get("timeout", 30.0),
        depends_on=service_data.get("depends_on", []),
    )


def _load_and_validate_services(group: str) -> tuple[list[_ServiceBuilder], Path, str]:
    """Load and validate services for a group.

    Args:
        group: Name of the group to load
    """
    config_manager = get_config_manager()

    init_group = config_manager.get_init_group(group)
    if not init_group:
        available = config_manager.list_init_groups()
        raise ValueError(f"Group '{group}' not found. Available groups: {', '.join(available) or 'none'}")

    config_file = config_manager._config_file
    config_dir = config_file.parent if config_file else Path.cwd()

    services = []
    for i, service_config in enumerate(init_group.services):
        builder = _ServiceBuilder(
            name=service_config.name,
            group=service_config.group,
            pane_index=service_config.pane,
            command=service_config.command,
            path=Path(service_config.path) if service_config.path else None,
            env=service_config.env or {},
            ready_pattern=service_config.ready_pattern,
            timeout=service_config.timeout or 30.0,
            depends_on=service_config.depends_on or [],
        )
        services.append(builder)

    all_errors = []
    for service in services:
        errors = service.validate(config_dir)
        if errors:
            all_errors.extend([f"{service.full_name}: {e}" for e in errors])

    if all_errors:
        raise ValueError("Validation failed:\n" + "\n".join(all_errors))

    return services, config_dir, init_group.layout


def _sort_by_dependencies(services: list[_ServiceBuilder]) -> list[_ServiceBuilder]:
    """Sort services by dependencies (topological sort).

    Args:
        services: List of services to sort
    """
    sorted_services = []
    remaining = services.copy()

    while remaining:
        ready = []
        for service in remaining:
            if not service.depends_on:
                ready.append(service)
            else:
                deps_met = all(any(s.name == dep for s in sorted_services) for dep in service.depends_on)
                if deps_met:
                    ready.append(service)

        if not ready:
            names = [s.name for s in remaining]
            raise ValueError(f"Circular dependency detected among: {', '.join(names)}")

        for service in ready:
            sorted_services.append(service)
            remaining.remove(service)

    return sorted_services


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "description": "Run a development environment from configuration",
        "tags": {"orchestration", "services"},
    },
)
def run(state, group: str) -> dict[str, Any]:
    """Run a development environment from configuration.

    Creates a tmux session with multiple panes and starts services
    in dependency order. Uses the pane-centric architecture for
    all operations.

    Args:
        state: Application state (unused).
        group: Name of the group to run.

    Returns:
        Markdown formatted result with environment startup status.
    """
    elements = []

    try:
        services, config_dir, layout = _load_and_validate_services(group)

        if session_exists(group):
            return {
                "elements": [
                    {"type": "heading", "content": "Session Already Exists", "level": 2},
                    {"type": "text", "content": f"Session '{group}' is already running."},
                    {"type": "text", "content": f"Use `kill('{group}')` to stop it first."},
                ],
                "frontmatter": {"status": "error", "group": group},
            }

        services = _sort_by_dependencies(services)

        elements.append({"type": "heading", "content": f"Starting {group}", "level": 2})

        pane_id, swp = create_session(group)
        elements.append({"type": "text", "content": f"✓ Created session '{group}'"})

        max_pane = max((s.pane_index for s in services), default=0)
        num_panes = max_pane + 1

        if num_panes > 1:
            pane_ids = create_panes_with_layout(group, num_panes, layout)
            elements.append({"type": "text", "content": f"✓ Created {num_panes} panes with {layout} layout"})
        else:
            pane_ids = [pane_id]

        elements.append({"type": "heading", "content": "Starting Services", "level": 3})

        failed = False
        service_status = []

        for service in services:
            pane = Pane(pane_ids[service.pane_index])

            command = service.build_command(config_dir)

            result = send_command(
                pane,
                command,
                wait=bool(service.ready_pattern),
                timeout=service.timeout,
                ready_pattern=service.ready_pattern,
            )

            status = result.get("status", "unknown")

            if status in ["completed", "running"]:
                icon = "✓"
                service_status.append({"name": service.name, "target": service.target, "status": status})
            else:
                icon = "✗"
                failed = True
                service_status.append(
                    {"name": service.name, "target": service.target, "status": status, "error": result.get("error")}
                )

            elements.append({"type": "text", "content": f"{icon} {service.name}: {status}"})

            if failed:
                break

        elements.append({"type": "heading", "content": "Summary", "level": 3})

        if not failed:
            service_list = [f"• `{s['name']}` → `{s['target']}`" for s in service_status]

            elements.extend(
                [
                    {"type": "list", "items": service_list, "ordered": False},
                    {"type": "text", "content": ""},
                    {"type": "text", "content": "Target services with:"},
                    {
                        "type": "code_block",
                        "content": f'execute("ps aux", "{group}.backend")\nread("{group}.frontend")',
                        "language": "python",
                    },
                ]
            )

            status = "success"
        else:
            elements.append(
                {"type": "text", "content": f"Failed to start all services. Run `kill('{group}')` to clean up."}
            )
            status = "error"

        return {
            "elements": elements,
            "frontmatter": {"status": status, "group": group, "services": len(services), "layout": layout},
        }

    except ValueError as e:
        return {
            "elements": [
                {"type": "heading", "content": "Configuration Error", "level": 2},
                {"type": "text", "content": str(e)},
            ],
            "frontmatter": {"status": "error", "group": group},
        }
    except Exception as e:
        # Clean up session on unexpected error
        try:
            if session_exists(group):
                kill_session(group)
        except Exception:
            pass

        return {
            "elements": [
                {"type": "heading", "content": "Unexpected Error", "level": 2},
                {"type": "text", "content": f"Error: {e}"},
                {"type": "text", "content": "Session has been cleaned up if it was created."},
            ],
            "frontmatter": {"status": "error", "group": group},
        }


@app.command(
    display="table",
    headers=["Group", "Services", "Layout", "Status"],
    fastmcp={"enabled": False},
)
def run_list(state) -> list[dict]:
    """List available run configurations.

    Args:
        state: Application state (unused).

    Returns:
        Table data with group information.
    """
    try:
        config_manager = get_config_manager()

        rows = []
        for group_name in config_manager.list_init_groups():
            group = config_manager.get_init_group(group_name)
            if group:
                status = "running" if session_exists(group_name) else "stopped"

                rows.append(
                    {"Group": group_name, "Services": len(group.services), "Layout": group.layout, "Status": status}
                )

        return rows

    except Exception as e:
        return [{"Group": "Error", "Services": 0, "Layout": "", "Status": str(e)}]


@app.command(
    display="text",
    fastmcp={"enabled": False},
)
def kill(state, session: str) -> str:
    """Stop a running environment (kill tmux session).

    Args:
        state: Application state (unused).
        session: Name of the session to kill.

    Returns:
        Status message.
    """
    try:
        if kill_session(session):
            return f"✓ Stopped '{session}'"
        else:
            return f"Session '{session}' not found"
    except Exception as e:
        return f"Failed to stop session: {e}"
