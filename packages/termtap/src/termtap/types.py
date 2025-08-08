"""Type definitions for termtap - pane-first architecture.

Everything happens in panes. Sessions are just containers for organizing panes.
Target resolution is explicit and unambiguous.

PUBLIC API:
  - Target: Union type for flexible pane targeting
  - SessionWindowPane: Canonical format (e.g., "session:0.0")
"""

from typing import TypedDict, NotRequired, Literal, TYPE_CHECKING
from dataclasses import dataclass, field
import re

if TYPE_CHECKING:
    pass


type PaneID = str
type SessionWindowPane = str
type Target = PaneID | SessionWindowPane | str

type CommandStatus = Literal["completed", "timeout", "aborted", "running", "ready"]

type ReadMode = Literal["direct", "stream", "since_command"]

KNOWN_SHELLS = frozenset(["bash", "zsh", "fish", "sh", "dash", "ksh", "tcsh", "csh"])

type ShellType = Literal["bash", "fish", "zsh", "sh", "dash", "ksh", "tcsh", "csh", "unknown"]


@dataclass
class _PaneIdentifier:
    """Parsed pane identifier with all components.

    Attributes:
        session: Session name from the identifier.
        window: Window index from the identifier.
        pane: Pane index from the identifier.
    """

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
    def parse(cls, target: str) -> "_PaneIdentifier":
        """Parse session:window.pane format.

        Args:
            target: String like "epic-swan:0.0" or "backend:1.2".

        Returns:
            _PaneIdentifier instance.

        Raises:
            ValueError: If format is invalid.
        """
        match = re.match(r"^([^:]+):(\d+)\.(\d+)$", target)
        if not match:
            raise ValueError(f"Invalid pane identifier format: {target}")

        session, window, pane = match.groups()
        return cls(session=session, window=int(window), pane=int(pane))


def _is_pane_id(target: str) -> bool:
    """Check if target is a tmux pane ID (%number).

    Args:
        target: String to check.
    """
    return target.startswith("%") and target[1:].isdigit()


def _is_session_window_pane(target: str) -> bool:
    """Check if target is session:window.pane format.

    Args:
        target: String to check.
    """
    try:
        _PaneIdentifier.parse(target)
        return True
    except ValueError:
        return False


def _classify_target(target: Target) -> tuple[Literal["pane_id", "swp", "service", "convenience"], str]:
    """Classify target string to its type and normalized value.

    Args:
        target: Any target string.

    Returns:
        Tuple of (target_type, normalized_value).
    """
    if _is_pane_id(target):
        return ("pane_id", target)
    elif _is_session_window_pane(target):
        return ("swp", target)
    elif "." in target and ":" not in target:
        return ("service", target)
    else:
        return ("convenience", target)


def _parse_convenience_target(target: str) -> tuple[str, int | None, int | None]:
    """Parse convenience formats into components.

    Args:
        target: Convenience format string.

    Returns:
        Tuple of (session, window, pane) where window/pane may be None.
    """
    if ":" not in target:
        return (target, None, None)

    parts = target.split(":", 1)
    session = parts[0]

    if "." in parts[1]:
        window, pane = parts[1].split(".", 1)
        return (session, int(window), int(pane))
    else:
        return (session, int(parts[1]), None)


@dataclass
class ExecutionConfig:
    """Resolved configuration for command execution.

    Attributes:
        session_window_pane: Target pane in canonical format.
        ready_pattern: Optional regex pattern to wait for.
        timeout: Optional timeout in seconds.
        compiled_pattern: Pre-compiled regex pattern.
    """

    session_window_pane: SessionWindowPane
    ready_pattern: str | None = None
    timeout: float | None = None
    compiled_pattern: re.Pattern[str] | None = None


@dataclass
class ServiceConfig:
    """Configuration for a service in an init group.

    Attributes:
        name: Service name (e.g., "backend").
        group: Group name (e.g., "demo").
        pane: Pane index within the group.
        command: Command to execute for this service.
        path: Working directory.
        env: Environment variables.
        ready_pattern: Optional regex pattern to wait for.
        timeout: Optional timeout in seconds.
        depends_on: List of service dependencies.
    """

    name: str
    group: str
    pane: int
    command: str
    path: str | None = None
    env: dict[str, str] | None = None
    ready_pattern: str | None = None
    timeout: float | None = None
    depends_on: list[str] | None = None

    @property
    def full_name(self) -> str:
        """Get full service name (group.name)."""
        return f"{self.group}.{self.name}"

    @property
    def session_window_pane(self) -> SessionWindowPane:
        """Get session:window.pane for this service."""
        return f"{self.group}:0.{self.pane}"


@dataclass
class InitGroup:
    """Configuration for an init group.

    Attributes:
        name: Group name.
        layout: Tmux layout style.
        services: List of services in this group.
    """

    name: str
    layout: str = "even-horizontal"
    services: list[ServiceConfig] = field(default_factory=list)

    def get_service(self, name: str) -> ServiceConfig | None:
        """Get service by name.

        Args:
            name: Service name to find.

        Returns:
            ServiceConfig if found, None otherwise.
        """
        for service in self.services:
            if service.name == name:
                return service
        return None


class _PaneRow(TypedDict):
    """Row data for pane listing.

    Attributes:
        Pane: Pane identifier in session:window.pane format.
        Shell: Shell type running in the pane.
        Process: First non-shell process name.
        State: Current pane state.
        Attached: Whether session is attached.
    """

    Pane: str
    Shell: str
    Process: str
    State: Literal["ready", "working", "unknown"]
    Attached: Literal["Yes", "No"]


class _PaneRowWithStatus(TypedDict):
    """Enhanced pane row with status icon.

    Attributes:
        Status: Status icon from replkit2.
        Pane: Pane identifier in session:window.pane format.
        Shell: Shell type running in the pane.
        Process: First non-shell process name.
        State: Current pane state.
        Attached: Whether session is attached.
    """

    Status: str
    Pane: str
    Shell: str
    Process: str
    State: Literal["ready", "working", "unknown"]
    Attached: Literal["Yes", "No"]


class _HoverPattern(TypedDict):
    """Pattern for triggering hover dialogs.

    Attributes:
        pattern: Regex pattern to match commands.
        message: Warning message to display.
        confirm: Whether confirmation is required.
    """

    pattern: str
    message: str
    confirm: NotRequired[bool]


@dataclass
class _HoverResult:
    """Result from hover dialog interaction.

    Attributes:
        confirmed: Whether user confirmed the action.
        cancelled: Whether user cancelled the action.
        message: Optional message from the interaction.
    """

    confirmed: bool
    cancelled: bool
    message: str | None = None
