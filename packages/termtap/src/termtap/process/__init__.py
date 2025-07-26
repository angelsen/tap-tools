"""Process detection and state inspection for termtap.

PUBLIC API:
- detect_process: Get ProcessInfo for a session
- detect_all_processes: Batch detection for multiple sessions
- interrupt_process: Handler-aware interrupt
"""

from .detector import detect_process, detect_all_processes, interrupt_process

__all__ = [
    "detect_process",
    "detect_all_processes",
    "interrupt_process",
]
