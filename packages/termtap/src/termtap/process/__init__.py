"""Process tree analysis for termtap pane-centric architecture.

PUBLIC API:
  - ProcessNode: Tree node with process information (from .tree)
  - get_process_tree: Build complete process tree from root PID (from .tree)
  - get_process_chain: Get main execution chain from root PID (from .tree)
  - get_all_processes: Scan all processes from /proc (from .tree)
  - build_tree_from_processes: Build tree from pre-scanned processes (from .tree)
  - ProcessHandler: Base abstract class for process handlers (from .handlers)
  - get_handler: Get appropriate handler for a process (from .handlers)
"""

from .tree import ProcessNode, get_process_tree, get_process_chain, get_all_processes, build_tree_from_processes
from .handlers import ProcessHandler, get_handler

__all__ = [
    "ProcessNode",
    "get_process_tree",
    "get_process_chain",
    "get_all_processes",
    "build_tree_from_processes",
    "ProcessHandler",
    "get_handler",
]
