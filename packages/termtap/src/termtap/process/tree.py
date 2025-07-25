"""Process tree analysis using /proc filesystem.

PUBLIC API:
  - get_process_tree: Build complete process tree from a root PID
  - get_process_chain: Get main execution chain (parent->child->grandchild)
  - ProcessNode: Tree node with process information
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ProcessNode:
    """Node in a process tree with full process information.
    
    Attributes:
        pid: Process ID
        name: Process name (comm)
        cmdline: Full command line with arguments
        state: Process state (R=running, S=sleeping, etc)
        ppid: Parent process ID
        children: List of child ProcessNodes
        wait_channel: Kernel wait channel (if available)
        fd_count: Number of open file descriptors
    """
    pid: int
    name: str
    cmdline: str
    state: str
    ppid: int
    children: List['ProcessNode'] = field(default_factory=list)
    wait_channel: Optional[str] = None
    fd_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        d = {
            "pid": self.pid,
            "name": self.name,
            "cmdline": self.cmdline,
            "state": self.state,
            "ppid": self.ppid,
        }
        if self.wait_channel:
            d["wait_channel"] = self.wait_channel
        if self.fd_count is not None:
            d["fd_count"] = self.fd_count
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d
    
    @property
    def is_running(self) -> bool:
        """Check if process is actively running."""
        return self.state == "R"
    
    @property
    def is_sleeping(self) -> bool:
        """Check if process is sleeping."""
        return self.state == "S"
    
    @property
    def has_children(self) -> bool:
        """Check if process has any children."""
        return bool(self.children)


def _read_proc_file(path: str, default: str = "") -> str:
    """Read a /proc file safely."""
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except (IOError, OSError) as e:
        logger.debug(f"Could not read {path}: {e}")
        return default


def _read_proc_file_bytes(path: str) -> bytes:
    """Read a /proc file as bytes."""
    try:
        with open(path, 'rb') as f:
            return f.read()
    except (IOError, OSError) as e:
        logger.debug(f"Could not read {path}: {e}")
        return b""


def _get_process_children(pid: int) -> List[int]:
    """Get direct children of a process."""
    children_str = _read_proc_file(f"/proc/{pid}/task/{pid}/children")
    if not children_str:
        return []
    
    try:
        return [int(p) for p in children_str.split()]
    except ValueError as e:
        logger.debug(f"Invalid PID in children for {pid}: {e}")
        return []


def _get_process_info(pid: int) -> Optional[ProcessNode]:
    """Get information about a single process."""
    try:
        # Get command name
        name = _read_proc_file(f"/proc/{pid}/comm")
        if not name:
            return None
        
        # Get full command line
        cmdline_bytes = _read_proc_file_bytes(f"/proc/{pid}/cmdline")
        cmdline = cmdline_bytes.decode('utf-8', 'replace').replace('\x00', ' ').strip()
        if not cmdline:
            cmdline = name  # Fallback to comm if cmdline is empty
        
        # Parse stat file for state and ppid
        stat_data = _read_proc_file(f"/proc/{pid}/stat")
        if not stat_data:
            return None
        
        # State is after the last ) in stat (handles processes with ) in name)
        right_paren = stat_data.rfind(')')
        if right_paren == -1:
            return None
        
        stat_fields = stat_data[right_paren + 1:].strip().split()
        if len(stat_fields) < 2:
            return None
        
        state = stat_fields[0]
        ppid = int(stat_fields[1])
        
        # Get wait channel
        wait_channel = _read_proc_file(f"/proc/{pid}/wchan")
        if wait_channel == "0":
            wait_channel = None
        
        # Count file descriptors
        fd_count = None
        try:
            import os
            fd_count = len(os.listdir(f"/proc/{pid}/fd"))
        except (OSError, IOError):
            pass
        
        return ProcessNode(
            pid=pid,
            name=name,
            cmdline=cmdline,
            state=state,
            ppid=ppid,
            wait_channel=wait_channel,
            fd_count=fd_count
        )
        
    except Exception as e:
        logger.debug(f"Error getting process info for PID {pid}: {e}")
        return None


def _build_tree_recursive(pid: int, visited: Optional[set] = None) -> Optional[ProcessNode]:
    """Recursively build process tree from a PID."""
    if visited is None:
        visited = set()
    
    # Prevent cycles
    if pid in visited:
        logger.warning(f"Cycle detected at PID {pid}")
        return None
    visited.add(pid)
    
    # Get this process info
    node = _get_process_info(pid)
    if not node:
        return None
    
    # Get children and build their trees
    child_pids = _get_process_children(pid)
    for child_pid in child_pids:
        child_node = _build_tree_recursive(child_pid, visited)
        if child_node:
            node.children.append(child_node)
    
    return node


def get_process_tree(root_pid: int) -> Optional[ProcessNode]:
    """Build complete process tree starting from a root PID.
    
    Args:
        root_pid: PID to start building tree from
        
    Returns:
        ProcessNode representing the root with all descendants,
        or None if the process doesn't exist
    """
    return _build_tree_recursive(root_pid)


def get_process_chain(root_pid: int) -> List[ProcessNode]:
    """Get the main execution chain from a root PID.
    
    Follows the first child at each level to build the main
    execution chain (e.g., bash -> python -> subprocess).
    
    Args:
        root_pid: PID to start from
        
    Returns:
        List of ProcessNodes from root to leaf process
    """
    chain = []
    current_pid = root_pid
    visited = set()
    
    while current_pid and current_pid not in visited:
        visited.add(current_pid)
        
        node = _get_process_info(current_pid)
        if not node:
            break
        
        chain.append(node)
        
        # Get first child to continue chain
        child_pids = _get_process_children(current_pid)
        if child_pids:
            current_pid = child_pids[0]
        else:
            break
    
    return chain


def _find_processes_by_name(root: ProcessNode, name: str) -> List[ProcessNode]:
    """Find all processes with a given name in the tree.
    
    Args:
        root: Root node to search from
        name: Process name to search for
        
    Returns:
        List of ProcessNodes with matching names
    """
    results = []
    
    if root.name == name:
        results.append(root)
    
    for child in root.children:
        results.extend(_find_processes_by_name(child, name))
    
    return results


def _get_leaf_processes(root: ProcessNode) -> List[ProcessNode]:
    """Get all leaf processes (processes with no children).
    
    Args:
        root: Root node to search from
        
    Returns:
        List of leaf ProcessNodes
    """
    if not root.children:
        return [root]
    
    leaves = []
    for child in root.children:
        leaves.extend(_get_leaf_processes(child))
    
    return leaves