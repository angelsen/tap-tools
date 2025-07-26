"""Process detection and state inspection for termtap.

Provides process tree analysis and handler-aware process management.
Combines low-level tree building (tree.py) with high-level detection (detector.py).

PUBLIC API:
  - detect_process: Get ProcessInfo for a session
  - detect_all_processes: Batch detection for multiple sessions
  - interrupt_process: Handler-aware interrupt
  - get_handler_for_session: Get handler for a session's process
  - ProcessNode: Process information node dataclass
  - get_process_tree: Build complete process tree from a root PID
  - get_process_chain: Get main execution chain (parent->child->grandchild)
  - get_all_processes: Scan all processes from /proc
  - build_tree_from_processes: Build tree from pre-scanned processes
"""

from .detector import detect_process, detect_all_processes, interrupt_process, get_handler_for_session
from .tree import ProcessNode, get_process_tree, get_process_chain, get_all_processes, build_tree_from_processes

__all__ = [
    "detect_process",
    "detect_all_processes",
    "interrupt_process",
    "get_handler_for_session",
    "ProcessNode",
    "get_process_tree",
    "get_process_chain",
    "get_all_processes",
    "build_tree_from_processes",
]
