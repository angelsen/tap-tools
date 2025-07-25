"""Type definitions for termtap using Python 3.12 features.

Focuses on types that represent unique identifiers, configuration structures,
and API contracts. Avoids duplicating information available through syscalls.
"""

from typing import TypedDict, NotRequired, Literal
from dataclasses import dataclass


# Tmux target identifiers - not derivable from syscalls
type SessionName = str  # e.g., "epic-swan", "my-session"
type PaneID = str      # e.g., "%42", "%55"
type WindowID = str    # e.g., "@12", "@24"
type SessionWindowPane = str  # e.g., "session:0.0", "session:1.2"
type Target = SessionName | PaneID | WindowID | SessionWindowPane

# Command execution - result types only, no tracking
type CommandStatus = Literal["completed", "timeout", "aborted", "running", "not_found", "unknown", "deprecated"]
type WatcherReason = Literal["silence", "timeout", "aborted", "pattern_abort", "pattern_complete"]


# Shell detection - needed to determine command wrapping strategy
type ShellType = Literal["bash", "fish", "zsh", "sh", "dash", "unknown"]
BASH_COMPATIBLE_SHELLS: frozenset[str] = frozenset({"bash", "sh", "dash"})


# Hover dialog - UI-specific, not derivable
type HoverMode = Literal["before", "pattern", "during", "complete"]
type HoverAction = Literal["execute", "edit", "cancel", "join", "abort", "finish", "rerun"]


# Configuration - from TOML files
type EnvironmentVars = dict[str, str]
type HoverPatterns = list[str]


class TargetConfigDict(TypedDict):
    """Raw configuration dictionary for a target."""
    dir: NotRequired[str]
    start: NotRequired[str]
    env: NotRequired[EnvironmentVars]
    hover_patterns: NotRequired[HoverPatterns]


# Display data structures - API contracts
class SessionRow(TypedDict):
    """Row data for sessions table."""
    Session: str
    Attached: Literal["Yes", "No"]


class ProcessRow(TypedDict):
    """Row data for session processes."""
    Session: str
    Process: str
    Command: str
    State: str


class DashboardData(TypedDict):
    """Complete dashboard data structure."""
    summary: str
    sessions: list[SessionRow]
    active: list[ProcessRow]
    targets: dict[str, list[str]]


# Result types for better error handling
@dataclass
class Ok[T]:
    """Success result wrapper."""
    value: T


@dataclass
class Err:
    """Error result wrapper."""
    error: str


type Result[T] = Ok[T] | Err


# Target type guards
def is_pane_id(target: str) -> bool:
    """Check if target is a pane ID format."""
    return target.startswith("%")


def is_window_id(target: str) -> bool:
    """Check if target is a window ID format."""
    return target.startswith("@")


def is_session_window_pane(target: str) -> bool:
    """Check if target is session:window.pane format."""
    return ":" in target and "." in target.split(":", 1)[1]


def parse_target(target: str) -> tuple[Literal["session", "pane", "window", "swp"], str]:
    """Parse target string and return its type and value."""
    match target:
        case s if is_pane_id(s):
            return ("pane", s)
        case s if is_window_id(s):
            return ("window", s)
        case s if is_session_window_pane(s):
            return ("swp", s)
        case _:
            return ("session", target)