"""Process tree analysis using /proc filesystem.

PUBLIC API:
  - ProcessNode: Tree node with process information (dataclass)
  - get_process_tree: Build complete process tree from a root PID
  - get_process_chain: Get main execution chain (parent->child->grandchild)
  - get_all_processes: Scan all processes from /proc (for batch operations)
  - build_tree_from_processes: Build tree from pre-scanned processes
"""

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

logger = logging.getLogger(__name__)


@dataclass
class ProcessNode:
    """Tree node with process information.

    Attributes:
        pid: Process ID.
        name: Process name (comm).
        cmdline: Full command line with arguments.
        state: Process state (R=running, S=sleeping, etc).
        ppid: Parent process ID.
        children: List of child ProcessNodes.
        wait_channel: Kernel wait channel (if available).
        fd_count: Number of open file descriptors.
    """

    pid: int
    name: str
    cmdline: str
    state: str
    ppid: int
    children: List["ProcessNode"] = field(default_factory=list)
    wait_channel: Optional[str] = None
    fd_count: Optional[int] = None

    def _to_dict(self) -> Dict[str, Any]:
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
            d["children"] = [c._to_dict() for c in self.children]
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
    """Read a /proc file safely.

    Args:
        path: Path to /proc file.
        default: Default value if read fails.
    """
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except (IOError, OSError) as e:
        logger.debug(f"Could not read {path}: {e}")
        return default


def _read_proc_file_bytes(path: str) -> bytes:
    """Read a /proc file as bytes.

    Args:
        path: Path to /proc file.
    """
    try:
        with open(path, "rb") as f:
            return f.read()
    except (IOError, OSError) as e:
        logger.debug(f"Could not read {path}: {e}")
        return b""


def get_all_processes() -> Dict[int, Dict[str, Any]]:
    """Scan all processes and extract their information.

    Returns:
        Dict mapping PID to process info including PPID.
    """
    processes = {}

    try:
        # List all numeric directories in /proc
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue

            pid = int(entry)
            info = _get_process_info(pid)
            if info:
                processes[pid] = {"node": info, "ppid": info.ppid}
    except OSError as e:
        logger.error(f"Error scanning /proc: {e}")

    return processes


def _get_process_info(pid: int) -> Optional[ProcessNode]:
    """Get information about a single process.

    Args:
        pid: Process ID to get info for.
    """
    try:
        # Get command name
        name = _read_proc_file(f"/proc/{pid}/comm")
        if not name:
            return None

        # Get full command line
        cmdline_bytes = _read_proc_file_bytes(f"/proc/{pid}/cmdline")
        cmdline = cmdline_bytes.decode("utf-8", "replace").replace("\x00", " ").strip()
        if not cmdline:
            cmdline = name  # Fallback to comm if cmdline is empty

        # Parse stat file for state and ppid
        stat_data = _read_proc_file(f"/proc/{pid}/stat")
        if not stat_data:
            return None

        # State is after the last ) in stat (handles processes with ) in name)
        right_paren = stat_data.rfind(")")
        if right_paren == -1:
            return None

        stat_fields = stat_data[right_paren + 1 :].strip().split()
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
            fd_count = len(os.listdir(f"/proc/{pid}/fd"))
        except (OSError, IOError):
            pass

        return ProcessNode(
            pid=pid, name=name, cmdline=cmdline, state=state, ppid=ppid, wait_channel=wait_channel, fd_count=fd_count
        )

    except Exception as e:
        logger.debug(f"Error getting process info for PID {pid}: {e}")
        return None


def build_tree_from_processes(processes: Dict[int, Dict[str, Any]], root_pid: int) -> Optional[ProcessNode]:
    """Build a tree structure from the flat process list.

    Args:
        processes: Dict mapping PID to process info.
        root_pid: PID to use as tree root.

    Returns:
        ProcessNode tree or None if root not found.
    """
    if root_pid not in processes:
        return None

    # Get root node
    root = processes[root_pid]["node"]

    # Build a map of ppid -> [children]
    children_map: Dict[int, List[int]] = {}
    for pid, info in processes.items():
        ppid = info["ppid"]
        if ppid not in children_map:
            children_map[ppid] = []
        children_map[ppid].append(pid)

    # Recursively attach children
    def _attach_children(node: ProcessNode, visited: Set[int]):
        """Recursively attach children to a node."""
        if node.pid in visited:
            return  # Prevent cycles
        visited.add(node.pid)

        if node.pid in children_map:
            for child_pid in sorted(children_map[node.pid]):
                if child_pid in processes and child_pid not in visited:
                    child_node = processes[child_pid]["node"]
                    node.children.append(child_node)
                    _attach_children(child_node, visited)

    visited: Set[int] = set()
    _attach_children(root, visited)

    return root


def get_process_tree(root_pid: int) -> Optional[ProcessNode]:
    """Build complete process tree starting from a root PID.

    Uses the pstree algorithm: scanning all processes and
    building relationships from PPID information.

    Args:
        root_pid: PID to start building tree from.

    Returns:
        ProcessNode representing the root with all descendants,
        or None if the process doesn't exist.
    """
    # Get all processes
    processes = get_all_processes()

    # Build tree from root
    return build_tree_from_processes(processes, root_pid)


def extract_chain_from_tree(tree: Optional[ProcessNode]) -> List[ProcessNode]:
    """Extract the main execution chain from a process tree.

    Follows the first child at each level to build the main
    execution chain (e.g., bash -> python -> subprocess).

    Args:
        tree: Root ProcessNode of the tree.

    Returns:
        List of ProcessNodes from root to leaf process.
    """
    if not tree:
        return []

    chain = []
    current = tree
    visited = set()

    while current and current.pid not in visited:
        visited.add(current.pid)
        chain.append(current)
        # Follow first child (main execution path)
        current = current.children[0] if current.children else None

    return chain


def get_process_chain(root_pid: int) -> List[ProcessNode]:
    """Get the main execution chain from a root PID.

    Follows the first child at each level to build the main
    execution chain (e.g., bash -> python -> subprocess).

    Args:
        root_pid: PID to start from.

    Returns:
        List of ProcessNodes from root to leaf process.
    """
    tree = get_process_tree(root_pid)
    return extract_chain_from_tree(tree)


def get_process_chains_batch(pids: List[int]) -> Dict[int, List[ProcessNode]]:
    """Get process chains for multiple PIDs with a single /proc scan.

    More efficient than calling get_process_chain multiple times.

    Args:
        pids: List of PIDs to get chains for.

    Returns:
        Dict mapping PID to its process chain.
    """
    # Single scan of all processes
    all_processes = get_all_processes()
    
    chains = {}
    for pid in pids:
        tree = build_tree_from_processes(all_processes, pid)
        chains[pid] = extract_chain_from_tree(tree)
    
    return chains


def extract_shell_and_process(
    chain: List[ProcessNode], skip_processes: List[str]
) -> tuple[Optional[ProcessNode], Optional[ProcessNode]]:
    """Extract shell and active process from chain.

    Args:
        chain: Process chain from root to leaf.
        skip_processes: Process names to skip when finding active process.

    Returns:
        (shell, process) where shell is the last shell in chain,
        process is first non-shell or None if at shell prompt.
    """
    from ..types import KNOWN_SHELLS
    
    if not chain:
        return None, None

    # Find last shell in chain
    shell = None
    for proc in chain:
        if proc.name in KNOWN_SHELLS:
            shell = proc

    # Find first non-skipped process
    # Skip all shells and configured skip processes
    skip = KNOWN_SHELLS.union(set(skip_processes))

    process = None
    for proc in chain:
        if proc.name not in skip:
            process = proc
            break

    # If no shell found and we have a process, it's a direct-launched process
    # (e.g., tmux new-session -s foo claude)
    if not shell and process:
        # The process is running directly without a shell
        return None, process

    # If no shell found and no process, fallback to root as shell
    if not shell:
        shell = chain[0] if chain else None

    return shell, process
