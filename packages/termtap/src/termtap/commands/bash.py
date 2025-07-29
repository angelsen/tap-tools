"""Bash command - owns the complete execution workflow."""

import time
from typing import Any

from ..app import app
from ..types import Target
from ..tmux import send_keys, send_via_buffer, resolve_or_create_target, CurrentPaneError, resolve_target
from ..process.detector import detect_process
from ..config import get_execution_config, get_config_manager
from ..errors import markdown_error_response


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": "Execute command in tmux pane"},
)
def bash(
    state,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Execute command in target pane."""
    # 1. Resolution - get or create single pane
    try:
        pane_id, session_window_pane = resolve_or_create_target(target)
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
                return markdown_error_response(message)
            except Exception:
                # Fallback to original error
                return markdown_error_response(f"Target error: {error_str}")

        # Handle service not found
        elif "Service" in error_str and "not found" in error_str:
            message = f"Service not found: {target}\nUse 'init_list()' to see available init groups."
            return markdown_error_response(message)

        # Generic target error
        else:
            return markdown_error_response(f"Target error: {error_str}")

    except Exception as e:
        # Catch any other unexpected errors
        return markdown_error_response(f"Unexpected error: {e}")

    try:
        # 2. Get config for ready patterns
        config = get_execution_config(session_window_pane)
        if timeout is None:
            timeout = config.timeout or 30.0

        # 3. Setup streaming
        stream = state.executor.stream_manager.get_stream(pane_id, session_window_pane)
        stream.start()

        # Mark command start for output tracking
        cmd_id = f"cmd_{int(time.time() * 1000)}"
        stream.mark_command(cmd_id, command)
    except Exception as e:
        return markdown_error_response(f"Failed to initialize command: {e}")

    # 4. Send command
    try:
        # Use buffer for multiline commands, send-keys for single-line
        if "\n" in command:
            send_via_buffer(pane_id, command)
        else:
            send_keys(pane_id, command)
    except CurrentPaneError:
        return markdown_error_response(f"Cannot send commands to current pane ({pane_id})")
    except RuntimeError as e:
        # Tmux operation failed
        return markdown_error_response(str(e))

    # Early return for non-wait
    if not wait:
        process_info = detect_process(pane_id)
        return {
            "elements": [{"type": "text", "content": f"Command started in pane {session_window_pane}"}],
            "frontmatter": {
                "command": command,
                "status": "running",
                "pane": session_window_pane,
                "process": process_info.process or process_info.shell,
            },
        }

    # 5. Wait for completion
    start_time = time.time()
    ready_match = None
    status = "timeout"  # Default if we hit timeout

    # Let process start
    time.sleep(0.1)

    while time.time() - start_time < timeout:
        # Get current output
        output = stream.read_command_output(cmd_id)

        # Check ready pattern
        if config.compiled_pattern and output:
            match = config.compiled_pattern.search(output)
            if match:
                ready_match = match.group(0)
                status = "ready"
                break

        # Check process state
        process_info = detect_process(pane_id)
        if process_info.state == "ready":
            status = "completed"
            break

        time.sleep(0.1)

    # Mark command end
    stream.mark_command_end(cmd_id)
    duration = time.time() - start_time

    # Get final output and process info
    output = stream.read_command_output(cmd_id)
    process_info = detect_process(pane_id)

    # 6. Build response
    elements = []

    # Main output
    elements.append(
        {"type": "code_block", "content": output or "[No output]", "language": process_info.process or "bash"}
    )

    # Status messages
    if status == "ready" and ready_match:
        elements.append(
            {"type": "blockquote", "content": f'Ready after {duration:.1f}s - Matched pattern: "{ready_match}"'}
        )
    elif status == "timeout":
        elements.append({"type": "blockquote", "content": f"Timeout after {duration:.1f}s"})

    return {
        "elements": elements,
        "frontmatter": {
            "command": command,
            "status": status,
            "duration": duration,
            "pane": session_window_pane,
            "process": process_info.process or process_info.shell,
        },
    }
