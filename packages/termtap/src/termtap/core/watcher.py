"""Radio silence and pattern detection algorithms.

PUBLIC API:
  None - all functions are internal utilities"""

import time
from typing import Optional, Callable, List, Tuple
from pathlib import Path

from ..tmux.stream import _StreamHandle


def _wait_for_silence(
    stream: _StreamHandle,
    cmd_id: str,
    silence_period: float = 1.0,
    timeout: Optional[float] = None,
    abort_check: Optional[Callable[[], bool]] = None,
) -> Tuple[str, str]:
    """Wait for radio silence in stream.

    Args:
        stream: Stream handle
        cmd_id: Command ID for position tracking
        silence_period: Seconds of no output to consider complete
        timeout: Optional timeout in seconds
        abort_check: Optional function to check for abort

    Returns:
        Tuple of (output, reason) where reason is one of:
        - "silence": Radio silence achieved
        - "timeout": Timeout reached
        - "aborted": Abort check returned True
    """
    start_time = time.time()
    last_pos = stream.positions.get(cmd_id, 0)
    last_change = time.time()

    while True:
        # Check abort condition
        if abort_check and abort_check():
            return stream.read_from(cmd_id), "aborted"

        # Check timeout
        if timeout and time.time() - start_time > timeout:
            return stream.read_from(cmd_id), "timeout"

        # Read new content
        new_content, new_pos = stream.read_new(last_pos)

        if new_content:
            # New data arrived, reset silence timer
            last_pos = new_pos
            last_change = time.time()
        elif time.time() - last_change >= silence_period:
            # Radio silence achieved
            return stream.read_from(cmd_id), "silence"

        time.sleep(0.1)


def _wait_with_patterns(
    stream: _StreamHandle,
    cmd_id: str,
    patterns: List[str],
    pattern_callback: Callable[[str, str], Optional[str]],
    silence_period: float = 1.0,
    timeout: Optional[float] = None,
    abort_check: Optional[Callable[[], bool]] = None,
) -> Tuple[str, str]:
    """Wait for silence with pattern detection.

    Args:
        stream: Stream handle
        cmd_id: Command ID for position tracking
        patterns: List of patterns to detect
        pattern_callback: Called when pattern found, returns action or None
                         Action can be: "abort", "complete", None (continue)
        silence_period: Seconds of no output to consider complete
        timeout: Optional timeout in seconds
        abort_check: Optional function to check for abort

    Returns:
        Tuple of (output, reason) where reason is one of:
        - "silence": Radio silence achieved
        - "timeout": Timeout reached
        - "aborted": Abort check returned True
        - "pattern_abort": Pattern callback returned "abort"
        - "pattern_complete": Pattern callback returned "complete"
    """
    start_time = time.time()
    last_pos = stream.positions.get(cmd_id, 0)
    last_change = time.time()

    while True:
        # Check abort condition
        if abort_check and abort_check():
            return stream.read_from(cmd_id), "aborted"

        # Check timeout
        if timeout and time.time() - start_time > timeout:
            return stream.read_from(cmd_id), "timeout"

        # Read new content
        new_content, new_pos = stream.read_new(last_pos)

        if new_content:
            # Check patterns in new content
            for pattern in patterns:
                if pattern in new_content:
                    # Get full output so far
                    full_output = stream.read_from(cmd_id)

                    # Call pattern callback
                    action = pattern_callback(pattern, full_output)

                    if action == "abort":
                        return full_output, "pattern_abort"
                    elif action == "complete":
                        return full_output, "pattern_complete"
                    # else continue waiting

            # New data arrived, reset silence timer
            last_pos = new_pos
            last_change = time.time()

        elif time.time() - last_change >= silence_period:
            # Radio silence achieved
            return stream.read_from(cmd_id), "silence"

        time.sleep(0.1)


def _create_abort_checker(session: str, project_id: str) -> Callable[[], bool]:
    """Create abort checker that looks for abort file.

    Args:
        session: Session name
        project_id: Project identifier

    Returns:
        Function that checks for abort file
    """
    abort_file = Path(f"/tmp/termtap/{project_id}/{session}.abort")

    def check():
        if abort_file.exists():
            abort_file.unlink()
            return True
        return False

    return check
