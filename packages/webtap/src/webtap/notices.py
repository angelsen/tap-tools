"""Notice management for multi-surface warnings.

PUBLIC API:
  - Notice: Notice dataclass
  - NoticeManager: Notice management singleton
  - NOTICE_TYPES: Notice type definitions
"""

import threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


NOTICE_TYPES = {
    "extension_installed": {
        "message": "Extension installed. Load unpacked extension from: {path}",
        "clear_on": None,
    },
    "extension_updated": {
        "message": "Extension updated. Close and reopen sidepanel to apply.",
        "clear_on": "extension_connect",
    },
    "extension_manifest_changed": {
        "message": "Extension updated. Reload extension in chrome://extensions",
        "clear_on": None,
    },
    "client_stale": {
        "message": "{client_type} ({version}) in {context} is outdated",
        "clear_on": None,
    },
}


@dataclass
class Notice:
    """Notice for multi-surface display.

    Attributes:
        type: Notice type key (must be in NOTICE_TYPES)
        message: Human-readable message
        clear_on: Event that clears this notice (or None for manual clear)
        remaining: Countdown before auto-clear (or None for persistent)
    """

    type: str
    message: str
    clear_on: Optional[str] = None
    remaining: Optional[int] = None


class NoticeManager:
    """Thread-safe notice management.

    Notices are identified by type (one notice per type).
    Adding a notice with existing type replaces it.
    """

    def __init__(self):
        self._notices: Dict[str, Notice] = {}
        self._lock = threading.Lock()

    def add(self, notice_type: str, **format_args) -> None:
        """Add a notice (replaces existing of same type).

        Args:
            notice_type: Notice type key (must be in NOTICE_TYPES)
            **format_args: Arguments for message formatting

        Raises:
            KeyError: If notice_type not in NOTICE_TYPES
        """
        template = NOTICE_TYPES[notice_type]
        notice = Notice(
            type=notice_type,
            message=template["message"].format(**format_args),
            clear_on=template.get("clear_on"),
            remaining=template.get("remaining"),
        )
        with self._lock:
            self._notices[notice_type] = notice

    def clear(self, notice_type: str) -> None:
        """Clear specific notice by type.

        Args:
            notice_type: Notice type to clear
        """
        with self._lock:
            self._notices.pop(notice_type, None)

    def clear_on_event(self, event: str) -> None:
        """Clear notices triggered by event.

        Args:
            event: Event name (e.g., 'extension_connect')
        """
        with self._lock:
            self._notices = {k: v for k, v in self._notices.items() if v.clear_on != event}

    def decrement_remaining(self) -> None:
        """Decrement remaining counters and clear at zero."""
        with self._lock:
            to_remove = []
            for key, notice in self._notices.items():
                if notice.remaining is not None:
                    notice.remaining -= 1
                    if notice.remaining <= 0:
                        to_remove.append(key)
            for key in to_remove:
                del self._notices[key]

    def get_all(self) -> List[Dict]:
        """Get all notices as dicts for state snapshot.

        Returns:
            List of notice dicts with type, message, clear_on, remaining
        """
        with self._lock:
            return [asdict(n) for n in self._notices.values()]


__all__ = ["Notice", "NoticeManager", "NOTICE_TYPES"]
