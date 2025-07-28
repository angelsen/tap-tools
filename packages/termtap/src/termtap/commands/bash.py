"""Bash command - owns the complete execution workflow."""

import time
from typing import Any

from ..app import app
from ..types import Target
from ..tmux import send_keys
from ..tmux.utils import resolve_target_to_pane
from ..process.detector import detect_process
from ..config import get_execution_config


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
    # 1. Resolution & Creation
    session_created = False
    pane_id: str
    session_window_pane: str

    try:
        resolved_pane_id, resolved_swp = resolve_target_to_pane(target)
        if resolved_pane_id is None or resolved_swp is None:
            raise RuntimeError("Failed to resolve target")
        pane_id = resolved_pane_id
        session_window_pane = resolved_swp
    except RuntimeError:
        # Create new session if it's a simple name
        if isinstance(target, str) and not (":" in target or target.startswith("%")):
            from ..tmux.session import _create_session

            pane_id, session_window_pane = _create_session(target, ".")
            session_created = True
        else:
            # Can't create this target format
            return {
                "elements": [{"type": "text", "content": f"Target not found: {target}"}],
                "frontmatter": {"command": command, "status": "error"},
            }

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

    # 4. Send command
    send_keys(pane_id, command)

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

    # Session creation message
    if session_created:
        session_name = target if isinstance(target, str) else "default"
        elements.append(
            {"type": "blockquote", "content": f"Session '{session_name}' not found. Creating new session..."}
        )

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
