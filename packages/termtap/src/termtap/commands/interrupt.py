"""Interrupt command - send Ctrl+C to panes."""

from ..app import app
from ..types import Target
from ..tmux import resolve_target_to_pane, CurrentPaneError, resolve_target
from ..process import interrupt_process
from ..config import get_config_manager
from ..errors import string_error_response


@app.command(fastmcp={"type": "tool", "description": "Send interrupt (Ctrl+C) to a pane"})
def interrupt(state, target: Target) -> str:
    """Send interrupt (Ctrl+C) to a pane."""
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        error_str = str(e)

        # Handle ambiguous target with service suggestions
        if "matches" in error_str and "panes" in error_str:
            try:
                panes = resolve_target(target)
                targets = [swp for _, swp in panes]

                # Add service targets if available
                session = panes[0][1].split(":")[0]
                cm = get_config_manager()
                if session in cm._init_groups:
                    group = cm._init_groups[session]
                    targets.extend([s.full_name for s in group.services])

                message = f"Target '{target}' has {len(panes)} panes. Please specify:\n" + "\n".join(
                    f"  - {t}" for t in targets
                )
                return string_error_response(message)
            except Exception:
                # Fallback to original error
                return string_error_response(f"Target error: {error_str}")

        # Handle service not found
        elif "Service" in error_str and "not found" in error_str:
            message = f"Service not found: {target}\nUse 'init_list()' to see available init groups."
            return string_error_response(message)

        # Generic target error
        else:
            return string_error_response(f"Target error: {error_str}")

    except Exception as e:
        return string_error_response(f"Unexpected error: {e}")

    try:
        success, message = interrupt_process(pane_id)
        if success:
            return f"{session_window_pane}: {message}"
        return f"Failed to interrupt {session_window_pane}: {message}"
    except CurrentPaneError:
        return string_error_response(f"Cannot interrupt current pane ({pane_id})")
    except Exception as e:
        return string_error_response(f"Failed to send interrupt: {e}")
