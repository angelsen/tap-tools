"""Complex structure creation - handles multi-window/pane creation.

PUBLIC API:
  - get_or_create_session_with_structure: Get or create session with specific structure
"""

from .core import run_tmux, get_pane_id
from .session import session_exists, create_session


def get_or_create_session_with_structure(session: str, window: int, pane: int, start_dir: str = ".") -> tuple[str, str]:
    """Get or create session with specific window/pane structure.

    Args:
        session: Session name
        window: Window index (0-based)
        pane: Pane index (0-based)
        start_dir: Starting directory

    Returns:
        Tuple of (pane_id, session:window.pane)
    """
    # First check if the exact location exists
    swp = f"{session}:{window}.{pane}"
    pane_id = get_pane_id(session, str(window), str(pane))
    if pane_id:
        # Already exists
        return pane_id, swp

    # Check if session exists
    if not session_exists(session):
        # Create new session
        if window == 0 and pane == 0:
            # Simple case - just create session
            return create_session(session, start_dir)
        else:
            # Need to create session then add windows/panes
            pane_id, _ = create_session(session, start_dir)
            # Fall through to create additional structure

    # Session exists, check if we need to create window
    if window > 0:
        # Check if window exists
        code, _, _ = run_tmux(["list-windows", "-t", f"{session}:{window}", "-F", "#{window_index}"])
        if code != 0:
            # Create windows up to the target
            current_windows = _count_windows(session)
            for i in range(current_windows, window + 1):
                run_tmux(["new-window", "-t", f"{session}:", "-c", start_dir])

    # Now handle panes
    if pane > 0:
        # Check how many panes exist in target window
        code, stdout, _ = run_tmux(["list-panes", "-t", f"{session}:{window}", "-F", "#{pane_index}"])
        if code == 0:
            existing_panes = len(stdout.strip().split("\n")) if stdout.strip() else 0
            # Create additional panes
            for i in range(existing_panes, pane + 1):
                run_tmux(["split-window", "-t", f"{session}:{window}.{i - 1}", "-c", start_dir])

    # Get the final pane ID - need to filter to get exact pane
    code, stdout, _ = run_tmux(
        [
            "list-panes",
            "-t",
            swp,
            "-f",
            f"#{{==:#{{window_index}}.#{{pane_index}},{window}.{pane}}}",
            "-F",
            "#{pane_id}",
        ]
    )
    if code == 0:
        return stdout.strip(), swp
    else:
        raise RuntimeError(f"Failed to create pane at {swp}")


def _count_windows(session: str) -> int:
    """Count windows in a session.

    Args:
        session: Session name.
    """
    code, stdout, _ = run_tmux(["list-windows", "-t", session, "-F", "#{window_index}"])
    if code != 0:
        return 0
    return len(stdout.strip().split("\n")) if stdout.strip() else 0
