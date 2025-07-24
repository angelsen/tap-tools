"""Process detection and state inspection for termtap.

PUBLIC API:
- get_process_context: Get process context with shell and state info
- ProcessContext: Process context data class
"""

from .detect import get_process_context, ProcessContext

__all__ = [
    "get_process_context",
    "ProcessContext",
]
