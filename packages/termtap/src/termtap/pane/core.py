"""The Pane - pure data with lazy-loaded properties."""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..process.tree import ProcessNode

@dataclass
class Pane:
    """A tmux pane - the fundamental unit of termtap."""
    
    pane_id: str  # %42 - the only required input
    
    # Everything else is lazy-loaded
    _session_window_pane: Optional[str] = field(default=None, init=False)
    _pid: Optional[int] = field(default=None, init=False)
    _process_chain: Optional[list["ProcessNode"]] = field(default=None, init=False)
    _shell: Optional["ProcessNode"] = field(default=None, init=False)
    _process: Optional["ProcessNode"] = field(default=None, init=False)
    
    @property
    def session_window_pane(self) -> str:
        """Get session:window.pane format."""
        if self._session_window_pane is None:
            from ..tmux.core import run_tmux
            code, stdout, _ = run_tmux(["display-message", "-p", "-t", self.pane_id, 
                                       "#{session_name}:#{window_index}.#{pane_index}"])
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
        """Get process chain."""
        if self._process_chain is None:
            from ..process.tree import get_process_chain
            self._process_chain = get_process_chain(self.pid)
        return self._process_chain
    
    @property
    def shell(self) -> Optional["ProcessNode"]:
        """Get shell process."""
        if self._shell is None:
            from ..process import extract_shell_and_process
            from ..config import get_config_manager
            self._shell, self._process = extract_shell_and_process(
                self.process_chain, 
                get_config_manager().skip_processes
            )
        return self._shell
    
    @property
    def process(self) -> Optional["ProcessNode"]:
        """Get active process (non-shell)."""
        if self._process is None:
            _ = self.shell  # Trigger extraction
        return self._process
    
    def refresh(self) -> None:
        """Clear all cached data."""
        self._process_chain = None
        self._shell = None
        self._process = None
        self._pid = None