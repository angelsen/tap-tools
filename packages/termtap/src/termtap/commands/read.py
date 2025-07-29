"""Read command - clean pane output reading."""

from typing import Any

from ..app import app
from ..types import Target, ReadMode
from ..tmux import capture_visible, capture_all, capture_last_n, resolve_target
from ..process.detector import detect_process, detect_all_processes
from ..errors import markdown_error_response


@app.command(
    display="markdown",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux pane",
        "uri": "bash://{target}/{lines}",
    },
)
def read(
    state,
    target: Target = "default",
    lines: int | None = None,
    mode: ReadMode = "direct",
) -> dict[str, Any]:
    """Read output from target pane(s)."""
    # 1. Resolve target - may return multiple panes
    try:
        panes = resolve_target(target)
    except RuntimeError as e:
        error_str = str(e)

        # Handle service not found
        if "Service" in error_str and "not found" in error_str:
            message = f"Service not found: {target}\nUse 'init_list()' to see available init groups."
            return markdown_error_response(message)

        # Handle target not found
        elif "not found" in error_str or "No panes found" in error_str:
            return markdown_error_response(f"Target not found: {target}")

        # Generic target error
        else:
            return markdown_error_response(f"Target error: {error_str}")

    except Exception as e:
        return markdown_error_response(f"Unexpected error: {e}")

    if not panes:
        return markdown_error_response(f"No panes found for target: {target}")

    # Single pane - current behavior
    if len(panes) == 1:
        pane_id, session_window_pane = panes[0]

        try:
            # 2. Read content based on mode
            if mode == "stream":
                stream = state.executor.stream_manager.get_stream(pane_id, session_window_pane)

                if not stream.is_active() and not stream.is_running():
                    stream.start()
                    content = "[Stream starting - no content yet]"
                    lines_read = 0
                else:
                    content = stream.read_since_user_last()
                    stream.mark_user_read()
                    lines_read = len(content.splitlines()) if content else 0
            else:
                # Direct tmux capture
                if lines == -1:
                    content = capture_all(pane_id)
                elif lines:
                    content = capture_last_n(pane_id, lines)
                else:
                    content = capture_visible(pane_id)

                lines_read = len(content.splitlines()) if content else 0

            # 3. Detect process
            info = detect_process(pane_id)
            process = info.process or info.shell

            # 4. Build response
            return {
                "elements": [{"type": "code_block", "content": content or "[No output]", "language": process}]
                + ([{"type": "text", "content": f"Stream mode: {lines_read} new lines"}] if mode == "stream" else []),
                "frontmatter": {"pane": session_window_pane, "process": process, "lines": lines_read, "mode": mode},
            }
        except Exception as e:
            return markdown_error_response(f"Failed to read pane content: {e}")

    # Multiple panes - show all
    else:
        if mode == "stream":
            return markdown_error_response("Stream mode not supported for multiple panes")

        try:
            # Detect all processes
            pane_ids = [pid for pid, _ in panes]
            process_infos = detect_all_processes(pane_ids)

            elements = []
            total_lines = 0

            for pane_id, swp in panes:
                try:
                    # Capture content
                    if lines == -1:
                        content = capture_all(pane_id)
                    elif lines:
                        content = capture_last_n(pane_id, lines)
                    else:
                        content = capture_visible(pane_id)

                    lines_read = len(content.splitlines()) if content else 0
                    total_lines += lines_read

                    # Get process info
                    info = process_infos.get(pane_id)
                    process = info.process or info.shell if info else "bash"

                    # Add heading and content for each pane
                    elements.append({"type": "heading", "content": f"Pane: {swp}", "level": 3})
                    elements.append({"type": "code_block", "content": content or "[No output]", "language": process})
                except Exception as e:
                    # Log error for this pane but continue with others
                    elements.append({"type": "heading", "content": f"Pane: {swp}", "level": 3})
                    elements.append({"type": "text", "content": f"[Error reading pane: {e}]"})

            return {
                "elements": elements,
                "frontmatter": {"target": target, "panes": len(panes), "total_lines": total_lines, "mode": mode},
            }
        except Exception as e:
            return markdown_error_response(f"Failed to read multiple panes: {e}")
