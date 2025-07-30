"""Bash command - owns the complete execution workflow with handler hooks."""

import time
from typing import Any

from ..app import app
from ..types import Target, ProcessContext
from ..tmux import (
    send_keys,
    send_via_paste_buffer,
    resolve_or_create_target,
    CurrentPaneError,
    resolve_target,
    get_pane_pid,
)
from ..process.detector import detect_process
from ..process.tree import get_process_chain
from ..process.handlers import get_handler
from ..config import get_execution_config, get_config_manager
from ..errors import markdown_error_response


def _serialize_command(command: str, max_length: int = 40) -> str:
    """Serialize command for frontmatter display."""
    # Replace newlines with literal \n
    serialized = command.replace("\n", "\\n")

    # Truncate if too long
    if len(serialized) > max_length:
        return serialized[: max_length - 3] + "..."

    return serialized


def _get_shell_and_process(pane_id: str):
    """Get shell and active process for the pane."""
    pid = get_pane_pid(pane_id)
    chain = get_process_chain(pid)

    if not chain:
        return None, None

    config_manager = get_config_manager()
    skip_processes = config_manager.skip_processes

    # Find last shell in chain
    shell = None
    from ..types import KNOWN_SHELLS

    for proc in chain:
        if proc.name in KNOWN_SHELLS:
            shell = proc

    # Find first non-shell, non-skipped process
    skip = KNOWN_SHELLS.union(set(skip_processes))
    process = None
    for proc in chain:
        if proc.name not in skip:
            process = proc
            break

    # If no shell found and we have a process, it's direct-launched
    if not shell and process:
        return None, process

    # If no shell found and no process, fallback to root as shell
    if not shell:
        shell = chain[0]

    return shell, process


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
    """Execute command in target pane with full handler lifecycle."""
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

    # 2. Get config and timeout
    config = get_execution_config(session_window_pane)
    if timeout is None:
        timeout = config.timeout or 30.0

    # 3. Setup streaming
    stream = state.executor.stream_manager.get_stream(pane_id, session_window_pane)
    stream.start()

    # Mark command start for output tracking
    cmd_id = f"cmd_{int(time.time() * 1000)}"
    stream.mark_command(cmd_id, command)

    # 4. Get handler and create context if we have an active process
    shell, process = _get_shell_and_process(pane_id)
    handler = None
    ctx = None
    modified_command = command

    if process:
        # We have an active process - create context and get handler
        ctx = ProcessContext(pane_id=pane_id, process=process, session_window_pane=session_window_pane)
        handler = get_handler(ctx)

        # Call before_send hook
        modified_command = handler.before_send(ctx, command)
        if modified_command is None:
            return markdown_error_response("Command cancelled by handler")

    # 5. Send command
    try:
        if "\n" in modified_command:
            send_via_paste_buffer(pane_id, modified_command)
        else:
            send_keys(pane_id, modified_command)
    except CurrentPaneError:
        return markdown_error_response(f"Cannot send commands to current pane ({pane_id})")
    except RuntimeError as e:
        return markdown_error_response(str(e))

    # 6. Call after_send hook if we have a handler
    if handler and ctx:
        handler.after_send(ctx, modified_command)

    # Early return for non-wait
    if not wait:
        process_info = detect_process(pane_id)
        return {
            "elements": [{"type": "text", "content": f"Command started in pane {session_window_pane}"}],
            "frontmatter": {
                "command": _serialize_command(modified_command),
                "status": "running",
                "pane": session_window_pane,
                "process": process_info.process or process_info.shell,
            },
        }

    # 7. Wait for completion with during_command hook
    start_time = time.time()
    ready_match = None
    status = "timeout"  # Default if we hit timeout

    # Let process start
    time.sleep(0.1)

    while time.time() - start_time < timeout:
        elapsed = time.time() - start_time

        # Call during_command hook if we have a handler
        if handler and ctx:
            if not handler.during_command(ctx, elapsed):
                # Handler says stop waiting
                status = "completed"
                break

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

    # 8. Call after_complete hook if we have a handler
    if handler and ctx:
        handler.after_complete(ctx, modified_command, duration)

    # 9. Get final output and process info
    process_info = detect_process(pane_id)

    # Always render the final output to clean up ANSI sequences
    output = stream.read_command_output(cmd_id, as_displayed=True)

    # 10. Build response
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
            "command": _serialize_command(modified_command),
            "status": status,
            "duration": duration,
            "pane": session_window_pane,
            "process": process_info.process or process_info.shell,
        },
    }
