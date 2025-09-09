"""Python handler for REPL and script processes.

# to_agent: Required per handlers/README.md
TESTING LOG:
Date: 2025-08-07, Updated: 2025-08-25
System: Linux 6.12.39-1-lts, 6.12.43-1-lts
Process: python v3.12.11, python3, python3.11 (via uv), ipython v9.4.0, termtap v1.0, playwright
Tracking: ~/.termtap/tracking/20250807_212502_printTesting_system_Python
         ~/.termtap/tracking/20250807_212924_import_time_timesleep5
         ~/.termtap/tracking/20250807_212324_python
         ~/.termtap/tracking/20250730_000831_python3
         ~/.termtap/tracking/20250730_001146_uv_run_python
         ~/.termtap/tracking/20250807_234622_if_True______print
         ~/.termtap/tracking/20250825_174255_page___browser_conte (Playwright)

Observed wait_channels:
- do_select: Python REPL waiting for input (ready)
- do_sys_poll: Python REPL polling for input (ready)
- do_epoll_wait: IPython waiting for input (ready)
- do_wait: Python waiting for subprocess (working)
- hrtimer_nanosleep: Python during sleep/timing operations (working)

Notes:
- do_sys_poll is the most common ready state for Python 3.12.11
- do_select is used by termtap REPL for input waiting
- do_epoll_wait is specific to IPython interactive sessions
- hrtimer_nanosleep clearly indicates Python is executing time.sleep() or similar
- Both python3 and system python show same wait_channel patterns
- uv run python executes python3.11, system python is 3.12.11
- termtap is a Python REPL application running under uv
- IMPORTANT: Check wait_channel BEFORE has_children to support async operations
- Playwright keeps node subprocess running but Python shows do_select when ready
"""

from . import ProcessHandler
from ...pane import Pane


class _PythonHandler(ProcessHandler):
    """Handler for Python processes including REPL and scripts.

    Provides specialized handling for Python REPLs including smart
    indentation processing and wait channel detection.
    """

    _handles = ["python", "python3", "python3.11", "python3.12", "python3.13", "ipython", "termtap", "webtap"]

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages Python processes."""
        return bool(pane.process and pane.process.name in self._handles)

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Determine if Python is ready for input using wait channel patterns.

        Args:
            pane: Pane with process information.
        """
        if not pane.process:
            return True, "at shell prompt"

        # Check wait_channel FIRST - most accurate indicator
        # Ready states
        if pane.process.wait_channel == "do_select":
            return True, "Python waiting for input"

        if pane.process.wait_channel == "do_sys_poll":
            return True, "Python polling for input"

        if pane.process.wait_channel == "do_epoll_wait":
            return True, "IPython waiting for input"

        # Working states - Python is busy
        if pane.process.wait_channel == "do_wait":
            return False, "waiting for subprocess"

        if pane.process.wait_channel == "hrtimer_nanosleep":
            return False, "executing sleep/timing operation"

        # Only check children as fallback for unknown wait_channels
        if pane.process.has_children:
            return False, "has subprocess"

        return None, f"unrecognized wait_channel: {pane.process.wait_channel}"

    def send_to_pane(self, pane: Pane, command: str) -> bool:
        """Send command with chunking for Python 3.13 multiline paste.

        Splits multiline commands into logical chunks and sends them
        separately with readiness checking between chunks.

        Args:
            pane: Target pane.
            command: Command to send.

        Returns:
            True if sent successfully.
        """
        import time
        from ...tmux.pane import send_keys as tmux_send_keys, send_via_paste_buffer

        # Determine grace period based on subprocess presence
        grace_period = 0.5  # Default
        if pane.process and pane.process.children:
            for child in pane.process.children:
                if child.name == "node":
                    # Async browser operations need more settle time
                    grace_period = 1.5
                    break

        # Single line - handle directly without chunking
        if "\n" not in command:
            # Single-line compound statements need extra newline
            if self._is_compound_statement(command):
                command = command + "\n"

            # Send the command (with extra newline if needed) plus Enter
            success = tmux_send_keys(pane.pane_id, command, enter=True)

            # Grace period for single-line commands
            if success:
                time.sleep(grace_period)

            return success

        # Multiline - chunk and send with delays
        chunks = self._split_into_chunks(command)

        for i, chunk in enumerate(chunks):
            # Wait for ready between chunks (not before first)
            if i > 0:
                # Wait indefinitely - user can intervene manually if needed
                if not self._wait_for_ready(pane):
                    return False

            if "\n" in chunk:
                # Multi-line chunk - use paste buffer
                success = send_via_paste_buffer(pane.pane_id, chunk, enter=True)
                if not success:
                    return False

                # Check if chunk ends with indented code (needs extra Enter)
                lines = chunk.split("\n")
                last_non_empty = None
                for line in reversed(lines):
                    if line.strip():
                        last_non_empty = line
                        break

                if last_non_empty and last_non_empty[0] in " \t":
                    # Indented block needs extra Enter to execute
                    tmux_send_keys(pane.pane_id, "", enter=True)  # Send blank line
            else:
                # Single line chunk - just use send_keys
                success = tmux_send_keys(pane.pane_id, chunk, enter=True)
                if not success:
                    return False

        # Grace period after all chunks are sent
        time.sleep(grace_period)

        return True

    def _wait_for_ready(self, pane: Pane, timeout: float | None = None) -> bool:
        """Wait for Python REPL to be ready for input.

        Args:
            pane: Pane to check
            timeout: Optional timeout in seconds. None means wait indefinitely.
        """
        import time

        start = time.time()

        while True:
            ready, _ = self.is_ready(pane)
            if ready:
                return True

            # Check timeout if specified
            if timeout is not None and time.time() - start > timeout:
                return False

            time.sleep(0.2)

    def _is_compound_statement(self, command: str) -> bool:
        """Check if single-line command is a compound statement.

        Compound statements in Python REPL need an extra Enter to execute
        when written on a single line with a colon.

        Args:
            command: Single-line command to check.

        Returns:
            True if this needs to be treated as multi-line.
        """
        stripped = command.strip()

        # Must have a colon to be a compound statement
        if ":" not in stripped:
            return False

        # Check for compound statement keywords
        # These need extra Enter when followed by ":"
        compound_starts = [
            "if ",
            "elif ",
            "else:",
            "for ",
            "while ",
            "def ",
            "class ",
            "with ",
            "try:",
            "except ",
            "finally:",
            "async def ",
            "async for ",
            "async with ",
        ]

        for start in compound_starts:
            if stripped.startswith(start):
                return True

        return False

    def _split_into_chunks(self, command: str) -> list[str]:
        """Split command into logical chunks for separate execution.

        Simple indentation-based chunking:
        - Chunks complete when indentation returns to base level
        - Special handling for compound keywords (elif, else, except, finally)
        - Closing brackets/parens stay with their structure
        - Keeps multi-line data structures together naturally

        Returns list of command strings to send separately.
        """
        # Remove empty lines for pattern detection
        lines = [line for line in command.split("\n") if line.strip()]

        if not lines:
            return []

        # Keywords that continue compound statements (must stay with parent block)
        compound_keywords = {"elif", "else", "except", "finally"}
        # Closing tokens that should stay with their opening structure
        closing_tokens = {"]", "}", ")", "],", "},", "),"}

        chunks = []
        current_chunk = []
        base_indent: int | None = None

        for line in lines:
            stripped = line.strip()

            # Calculate indentation level (count spaces/tabs at start)
            indent_level = len(line) - len(line.lstrip())

            # Check if this is a compound continuation
            is_compound = any(
                stripped.startswith(kw + ":") or stripped.startswith(kw + " ") for kw in compound_keywords
            )

            # Check if this is just a closing bracket/paren
            is_closing = stripped in closing_tokens

            # First line or continuing current chunk?
            if not current_chunk or base_indent is None:
                current_chunk.append(line)
                base_indent = indent_level

            # Compound keyword at base level - keep with current chunk
            elif is_compound and indent_level == base_indent:
                current_chunk.append(line)

            # Closing bracket at base level - keep with current chunk
            elif is_closing and indent_level == base_indent:
                current_chunk.append(line)

            # Indented relative to base - keep in chunk
            elif indent_level > base_indent:
                current_chunk.append(line)

            # Back to base level or less - start new chunk
            elif indent_level <= base_indent:
                # Complete current chunk
                chunks.append("\n".join(current_chunk))
                # Start new chunk
                current_chunk = [line]
                base_indent = indent_level

        # Flush final chunk
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _apply_filters(self, raw_output: str) -> str:
        """Apply minimal filtering for Python REPL output.

        Args:
            raw_output: Raw captured output.
        """
        from ...filters import strip_trailing_empty_lines

        return strip_trailing_empty_lines(raw_output)
