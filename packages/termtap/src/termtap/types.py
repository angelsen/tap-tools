"""Type definitions for termtap - pane-first architecture.

Everything happens in panes. Sessions are just containers for organizing panes.
Target resolution is explicit and unambiguous.
"""

from typing import TypedDict, NotRequired, Literal
from dataclasses import dataclass
import re


# Pane-first identifiers
type PaneID = str  # e.g., "%42", "%55" - tmux native pane ID
type SessionWindowPane = str  # e.g., "session:0.0", "session:1.2" - our canonical format
type Target = PaneID | SessionWindowPane | str  # str for convenience resolution

# Command execution states
type CommandStatus = Literal["completed", "timeout", "aborted", "running"]

# Read mode types (start simple, add others when needed)
type ReadMode = Literal["direct", "stream", "since_command"]

# Known shells - single source of truth
KNOWN_SHELLS = frozenset(["bash", "zsh", "fish", "sh", "dash", "ksh", "tcsh", "csh"])

# Shell types for command wrapping (includes "unknown" for unrecognized shells)
type ShellType = Literal["bash", "fish", "zsh", "sh", "dash", "ksh", "tcsh", "csh", "unknown"]


@dataclass
class PaneIdentifier:
    """Parsed pane identifier with all components."""
    session: str
    window: int
    pane: int
    
    @property
    def swp(self) -> SessionWindowPane:
        """Get session:window.pane format."""
        return f"{self.session}:{self.window}.{self.pane}"
    
    @property
    def display(self) -> str:
        """Get display format for ls() output."""
        return self.swp
    
    @classmethod
    def parse(cls, target: str) -> "PaneIdentifier":
        """Parse session:window.pane format.
        
        Args:
            target: String like "epic-swan:0.0" or "backend:1.2"
            
        Returns:
            PaneIdentifier instance
            
        Raises:
            ValueError: If format is invalid
        """
        match = re.match(r'^([^:]+):(\d+)\.(\d+)$', target)
        if not match:
            raise ValueError(f"Invalid pane identifier format: {target}")
        
        session, window, pane = match.groups()
        return cls(session=session, window=int(window), pane=int(pane))


def is_pane_id(target: str) -> bool:
    """Check if target is a tmux pane ID (%number)."""
    return target.startswith('%') and target[1:].isdigit()


def is_session_window_pane(target: str) -> bool:
    """Check if target is session:window.pane format."""
    try:
        PaneIdentifier.parse(target)
        return True
    except ValueError:
        return False


def resolve_target(target: Target) -> tuple[Literal["pane_id", "swp", "convenience"], str]:
    """Resolve target to its type and normalized value.
    
    Args:
        target: Any target string
        
    Returns:
        Tuple of (target_type, normalized_value)
        - pane_id: Direct tmux pane ID like "%42"
        - swp: Explicit session:window.pane like "epic-swan:0.0"
        - convenience: Session name that needs resolution like "epic-swan"
    """
    if is_pane_id(target):
        return ("pane_id", target)
    elif is_session_window_pane(target):
        return ("swp", target)
    else:
        # Convenience format - might be session, session:window, or invalid
        return ("convenience", target)


def parse_convenience_target(target: str) -> tuple[str, int | None, int | None]:
    """Parse convenience formats into components.
    
    Supports:
    - "session" -> (session, None, None)
    - "session:1" -> (session, 1, None)
    - "session:1.2" -> (session, 1, 2)  # Already handled by resolve_target
    
    Args:
        target: Convenience format string
        
    Returns:
        Tuple of (session, window_or_none, pane_or_none)
    """
    if ':' not in target:
        return (target, None, None)
    
    parts = target.split(':', 1)
    session = parts[0]
    
    if '.' in parts[1]:
        # This is actually a full swp - shouldn't reach here
        window, pane = parts[1].split('.', 1)
        return (session, int(window), int(pane))
    else:
        # session:window format
        return (session, int(parts[1]), None)


# Process detection types
@dataclass
class ProcessInfo:
    """Information about a process in a pane."""
    shell: str
    process: str | None
    state: Literal["ready", "working", "unknown"]
    pane_id: str  # The pane this process is in


# Configuration types
@dataclass
class PaneConfig:
    """Configuration for a specific pane."""
    pane_id: SessionWindowPane
    dir: str | None = None
    start: str | None = None
    name: str | None = None  # Human-friendly name
    env: dict[str, str] | None = None


@dataclass
class SessionConfig:
    """Configuration for a session (applies to all its panes)."""
    session: str
    dir: str | None = None
    env: dict[str, str] | None = None


@dataclass
class TargetConfig:
    """Resolved configuration for a target."""
    target: SessionWindowPane  # Always resolved to explicit format
    dir: str
    env: dict[str, str]
    start: str | None = None
    name: str | None = None
    
    @property
    def absolute_dir(self) -> str:
        """Get absolute directory path."""
        import os
        return os.path.abspath(os.path.expanduser(self.dir))


# Note: Streaming metadata is stored directly in JSON sidecar files
# No need for in-memory types since sidecar is the source of truth


# Command result type
@dataclass
class CommandResult:
    """Result of command execution in a pane."""
    output: str
    status: CommandStatus
    pane_id: str  # Which pane it ran in
    session_window_pane: SessionWindowPane  # Full identifier
    process: str | None
    command_id: str  # Unique identifier for this command
    duration: float | None = None  # Execution time if waited
    start_time: float | None = None  # When command started


# Display types for ls() command
class PaneRow(TypedDict):
    """Row data for pane listing."""
    Pane: str  # session:window.pane
    Shell: str
    Process: str
    State: Literal["ready", "working", "unknown"]
    Attached: Literal["Yes", "No"]


# Hover dialog types (for dangerous commands)
class HoverPattern(TypedDict):
    """Pattern for triggering hover dialogs."""
    pattern: str
    message: str
    confirm: NotRequired[bool]


@dataclass
class HoverResult:
    """Result from hover dialog interaction."""
    confirmed: bool
    cancelled: bool
    message: str | None = None