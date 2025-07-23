"""Process detection and state inspection for termtap."""

from .detect import (
    detect_shell,
    detect_shell_from_pane,
    get_current_program,
    get_process_context,
    ProcessContext,
)

from .state import (
    is_ready_for_input,
    get_process_state,
    wait_for_ready_state,
    ProcessState,
)

from .tree import (
    get_process_tree,
    get_process_info,
    ProcessInfo,
)

__all__ = [
    # Detection
    "detect_shell",
    "detect_shell_from_pane",
    "get_current_program", 
    "get_process_context",
    "ProcessContext",
    # State
    "is_ready_for_input",
    "get_process_state",
    "wait_for_ready_state",
    "ProcessState",
    # Tree
    "get_process_tree",
    "get_process_info",
    "ProcessInfo",
]