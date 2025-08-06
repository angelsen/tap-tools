"""Process detection and state inspection for termtap.

Provides process tree analysis and handler-aware process management.
Combines low-level tree building (tree.py) with high-level detection (detector.py).

PUBLIC API:
  - detect_process: Get ProcessInfo for a pane
  - detect_all_processes: Batch detection for multiple panes
  - interrupt_process: Handler-aware interrupt
  - get_handler_for_pane: Get handler for a pane's process
  - extract_shell_and_process: Extract shell and process from a process chain
  - ProcessNode: Process information node dataclass
  - get_process_tree: Build complete process tree from a root PID
  - get_process_chain: Get main execution chain (parent->child->grandchild)
  - extract_chain_from_tree: Extract chain from existing tree
  - get_process_chains_batch: Get chains for multiple PIDs with single scan
  - get_all_processes: Scan all processes from /proc
  - build_tree_from_processes: Build tree from pre-scanned processes
"""

from .detector import (
    detect_process,
    detect_all_processes,
    interrupt_process,
    get_handler_for_pane,
    extract_shell_and_process,
)
from .tree import (
    ProcessNode,
    get_process_tree,
    get_process_chain,
    get_all_processes,
    build_tree_from_processes,
    extract_chain_from_tree,
    get_process_chains_batch,
)

__all__ = [
    "detect_process",
    "detect_all_processes",
    "interrupt_process",
    "get_handler_for_pane",
    "extract_shell_and_process",
    "ProcessNode",
    "get_process_tree",
    "get_process_chain",
    "extract_chain_from_tree",
    "get_process_chains_batch",
    "get_all_processes",
    "build_tree_from_processes",
]
