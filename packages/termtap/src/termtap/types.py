"""Type definitions for termtap using Python 3.12 features.

Focuses on types that represent unique identifiers, configuration structures,
and API contracts. Avoids duplicating information available through syscalls.
"""

from typing import TypedDict, NotRequired, Literal
from dataclasses import dataclass


# Tmux target identifiers - not derivable from syscalls
type SessionName = str  # e.g., "epic-swan", "my-session"
type PaneID = str  # e.g., "%42", "%55"
type WindowID = str  # e.g., "@12", "@24"
type SessionWindowPane = str  # e.g., "session:0.0", "session:1.2"
type Target = SessionName | PaneID | WindowID | SessionWindowPane

# Command execution - result types only, no tracking
type CommandStatus = Literal["completed", "timeout", "aborted", "running", "not_found", "unknown", "deprecated"]
type WatcherReason = Literal["silence", "timeout", "aborted", "pattern_abort", "pattern_complete"]


# Shell detection - needed to determine command wrapping strategy
type ShellType = Literal["bash", "fish", "zsh", "sh", "dash", "unknown"]
_BASH_COMPATIBLE_SHELLS: frozenset[str] = frozenset({"bash", "sh", "dash"})


# Hover dialog - UI-specific, not derivable
type HoverMode = Literal["before", "pattern", "during", "complete"]
type HoverAction = Literal["execute", "edit", "cancel", "join", "abort", "finish", "rerun"]


# Configuration - from TOML files
type EnvironmentVars = dict[str, str]
type HoverPatterns = list[str]


class TargetConfigDict(TypedDict):
    """Raw configuration dictionary for a target.

    Attributes:
        dir: Working directory for the target.
        start: Initial command to run when starting target.
        env: Environment variables to set.
        hover_patterns: Patterns that trigger hover dialogs.
    """

    dir: NotRequired[str]
    start: NotRequired[str]
    env: NotRequired[EnvironmentVars]
    hover_patterns: NotRequired[HoverPatterns]


# Process detection results
@dataclass
class ProcessInfo:
    """Process detection result with shell and active process.

    Attributes:
        shell: Shell name (bash, fish, zsh, etc.).
        process: Active process name or None if at shell.
        state: Current process state.
    """

    shell: str
    process: str | None
    state: Literal["ready", "working", "unknown"]


# Display data structures - API contracts
class SessionRow(TypedDict):
    """Row data for sessions table.

    Attributes:
        Session: Session name.
        Shell: Shell type running in session.
        Process: Active process name, "-" if at shell prompt.
        State: Current process state.
        Attached: Whether session is currently attached.
    """

    Session: str
    Shell: str
    Process: str
    State: Literal["ready", "working", "unknown"]
    Attached: Literal["Yes", "No"]


class ProcessRow(TypedDict):
    """Row data for session processes.

    Attributes:
        Session: Session name.
        Process: Process name.
        Command: Command being executed.
        State: Current process state.
    """

    Session: str
    Process: str
    Command: str
    State: str


class DashboardData(TypedDict):
    """Complete dashboard data structure.

    Attributes:
        summary: Summary text for dashboard.
        sessions: List of session rows.
        active: List of active process rows.
        targets: Mapping of target names to their sessions.
    """

    summary: str
    sessions: list[SessionRow]
    active: list[ProcessRow]
    targets: dict[str, list[str]]


# Result types for better error handling
@dataclass
class Ok[T]:
    """Success result wrapper.

    Attributes:
        value: The successful result value.
    """

    value: T


@dataclass
class Err:
    """Error result wrapper.

    Attributes:
        error: Error message describing what went wrong.
    """

    error: str


type Result[T] = Ok[T] | Err


# Target type guards
def _is_pane_id(target: str) -> bool:
    """Check if target is a pane ID format.

    Args:
        target: Target string to check.

    Returns:
        True if target matches pane ID format (starts with %).
    """
    return target.startswith("%")


def _is_window_id(target: str) -> bool:
    """Check if target is a window ID format.

    Args:
        target: Target string to check.

    Returns:
        True if target matches window ID format (starts with @).
    """
    return target.startswith("@")


def _is_session_window_pane(target: str) -> bool:
    """Check if target is session:window.pane format.

    Args:
        target: Target string to check.

    Returns:
        True if target matches session:window.pane format.
    """
    return ":" in target and "." in target.split(":", 1)[1]


def _parse_target(target: str) -> tuple[Literal["session", "pane", "window", "swp"], str]:
    """Parse target string and return its type and value.

    Args:
        target: Target string to parse.

    Returns:
        Tuple of (target_type, original_value).
    """
    match target:
        case s if _is_pane_id(s):
            return ("pane", s)
        case s if _is_window_id(s):
            return ("window", s)
        case s if _is_session_window_pane(s):
            return ("swp", s)
        case _:
            return ("session", target)
