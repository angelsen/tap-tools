"""The Pane - pure data with lazy-loaded properties."""

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..process.tree import ProcessNode

# Thread-local storage for process scan context
_scan_context = threading.local()


@dataclass
class Pane:
    """A tmux pane - the fundamental unit of termtap."""

    pane_id: str  # %42 - the only required input

    # Cached properties - only stable things that don't change
    _session_window_pane: Optional[str] = field(default=None, init=False)
    _pid: Optional[int] = field(default=None, init=False)

    @property
    def session_window_pane(self) -> str:
        """Get session:window.pane format."""
        if self._session_window_pane is None:
            from ..tmux.core import run_tmux

            code, stdout, _ = run_tmux(
                ["display-message", "-p", "-t", self.pane_id, "#{session_name}:#{window_index}.#{pane_index}"]
            )
            if code != 0:
                raise RuntimeError(f"Failed to get session:window.pane for {self.pane_id}")
            self._session_window_pane = stdout.strip()
        return self._session_window_pane

    @property
    def pid(self) -> int:
        """Get pane PID."""
        if self._pid is None:
            from ..tmux.core import run_tmux

            code, stdout, _ = run_tmux(["display-message", "-p", "-t", self.pane_id, "#{pane_pid}"])
            if code != 0:
                raise RuntimeError(f"Failed to get PID for {self.pane_id}")
            self._pid = int(stdout.strip())
        return self._pid

    @property
    def process_chain(self) -> list["ProcessNode"]:
        """Get process chain - uses scan context if available."""
        # Check if we're in a scan context
        if hasattr(_scan_context, "chains"):
            return _scan_context.chains.get(self.pid, [])
        else:
            # No context, fetch directly
            from ..process.tree import get_process_chain

            return get_process_chain(self.pid)

    @property
    def shell(self) -> Optional["ProcessNode"]:
        """Get shell process - always fresh from process_chain."""
        from ..process.tree import extract_shell_and_process
        from ..config import get_config_manager

        shell, _ = extract_shell_and_process(self.process_chain, get_config_manager().skip_processes)
        return shell

    @property
    def process(self) -> Optional["ProcessNode"]:
        """Get active process (non-shell) - always fresh from process_chain."""
        from ..process.tree import extract_shell_and_process
        from ..config import get_config_manager

        _, process = extract_shell_and_process(self.process_chain, get_config_manager().skip_processes)
        return process

    @property
    def handler(self):
        """Get handler for the current process in this pane."""
        from ..process.handlers import get_handler

        return get_handler(self)

    @property
    def visible_content(self) -> str:
        """Get visible pane content - always fresh."""
        from ..tmux.pane import capture_visible

        return capture_visible(self.pane_id)


@contextmanager
def process_scan(*pane_ids: str):
    """Context manager for process scanning.

    All process access within this context uses the same scan data.

    Args:
        *pane_ids: Specific pane IDs to scan. If none provided, scans all.

    Example:
        # Single pane - fresh scan each time
        with process_scan(pane.pane_id):
            is_ready = pane.handler.is_ready(pane)

        # Multiple panes - one scan for all
        with process_scan():
            panes = [Pane(pid) for pid in pane_ids]
            infos = [get_process_info(p) for p in panes]
    """
    from ..process.tree import get_process_chains_batch
    from ..tmux.core import run_tmux

    # Get PIDs for the panes we care about
    if pane_ids:
        # Specific panes
        pids = []
        for pane_id in pane_ids:
            code, stdout, _ = run_tmux(["display-message", "-p", "-t", pane_id, "#{pane_pid}"])
            if code == 0:
                pids.append(int(stdout.strip()))
    else:
        # All panes
        code, stdout, _ = run_tmux(["list-panes", "-a", "-F", "#{pane_pid}"])
        if code == 0:
            pids = [int(line) for line in stdout.strip().split("\n") if line]
        else:
            pids = []

    # Single scan for all PIDs
    _scan_context.chains = get_process_chains_batch(pids) if pids else {}

    try:
        yield
    finally:
        # Clean up context
        if hasattr(_scan_context, "chains"):
            del _scan_context.chains
