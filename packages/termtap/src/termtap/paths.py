"""XDG path helpers for termtap daemon.

PUBLIC API:
  - get_runtime_dir: Runtime directory (sockets, PID)
  - get_config_dir: Config directory (patterns.yaml)
  - get_state_dir: State directory (logs)
  - SOCKET_PATH: Main daemon RPC socket
  - EVENTS_SOCKET_PATH: Event broadcast socket
  - COLLECTOR_SOCK_PATH: Stream collector socket
  - PID_PATH: PID file path
  - PATTERNS_PATH: Patterns file path
  - LOG_PATH: Log file path
"""

from pathlib import Path
from platformdirs import user_runtime_dir, user_config_dir, user_state_dir

__all__ = [
    "get_runtime_dir",
    "get_config_dir",
    "get_state_dir",
    "SOCKET_PATH",
    "EVENTS_SOCKET_PATH",
    "COLLECTOR_SOCK_PATH",
    "PID_PATH",
    "PATTERNS_PATH",
    "LOG_PATH",
]


def get_runtime_dir() -> Path:
    """Get runtime directory for sockets and PID file.

    Creates directory if it doesn't exist.
    """
    path = Path(user_runtime_dir("termtap"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir() -> Path:
    """Get config directory for config.yaml and patterns.yaml.

    Creates directory if it doesn't exist.
    """
    path = Path(user_config_dir("termtap"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_state_dir() -> Path:
    """Get state directory for logs.

    Creates directory if it doesn't exist.
    Streams are in memory, not files.
    """
    path = Path(user_state_dir("termtap"))
    path.mkdir(parents=True, exist_ok=True)
    return path


# Socket paths
SOCKET_PATH = get_runtime_dir() / "daemon.sock"
EVENTS_SOCKET_PATH = get_runtime_dir() / "events.sock"
COLLECTOR_SOCK_PATH = get_runtime_dir() / "collector.sock"

# PID file
PID_PATH = get_runtime_dir() / "daemon.pid"

# Config file
PATTERNS_PATH = get_config_dir() / "patterns.yaml"

# Log file
LOG_PATH = get_state_dir() / "termtap.log"
