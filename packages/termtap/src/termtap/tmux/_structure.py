"""Complex structure creation - handles multi-window/pane creation."""

from .core import run_tmux, _get_pane_id
from .session import session_exists, create_session


def _get_or_create_session_with_structure(
    session: str, window: int, pane: int, start_dir: str = "."
) -> tuple[str, str]:
    """Get or create session with specific window/pane structure.

    Args:
        session: Session name
        window: Window index (0-based)
        pane: Pane index (0-based)
        start_dir: Starting directory

    Returns:
        Tuple of (pane_id, session:window.pane)
    """
    swp = f"{session}:{window}.{pane}"
    pane_id = _get_pane_id(session, str(window), str(pane))
    if pane_id:
        return pane_id, swp

    if not session_exists(session):
        if window == 0 and pane == 0:
            return create_session(session, start_dir)
        else:
            pane_id, _ = create_session(session, start_dir)

    if window > 0:
        code, _, _ = run_tmux(["list-windows", "-t", f"{session}:{window}", "-F", "#{window_index}"])
        if code != 0:
            current_windows = _count_windows(session)
            for i in range(current_windows, window + 1):
                run_tmux(["new-window", "-t", f"{session}:", "-c", start_dir])

    if pane > 0:
        code, stdout, _ = run_tmux(["list-panes", "-t", f"{session}:{window}", "-F", "#{pane_index}"])
        if code == 0:
            existing_panes = len(stdout.strip().split("\n")) if stdout.strip() else 0
            for i in range(existing_panes, pane + 1):
                run_tmux(["split-window", "-t", f"{session}:{window}.{i - 1}", "-c", start_dir])

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
