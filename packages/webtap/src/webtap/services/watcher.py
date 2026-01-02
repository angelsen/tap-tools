"""Chrome availability watcher.

PUBLIC API:
  - ChromeWatcher: Background thread that monitors Chrome debug port
"""

import logging
import threading
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from webtap.services.main import WebTapService

logger = logging.getLogger(__name__)


class ChromeWatcher:
    """Background thread that monitors Chrome debug port availability.

    Polls the Chrome debug port every 5 seconds and broadcasts state changes
    via SSE so the extension can show "Waiting for Chrome..." or "Chrome ready".

    Does NOT auto-connect - just tracks availability. User calls connect() to pick a page.
    """

    def __init__(self, service: "WebTapService", port: int = 9222):
        self.service = service
        self.port = port
        self.available = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="chrome-watcher")

    def start(self) -> None:
        """Start the watcher thread."""
        self._thread.start()
        logger.debug(f"Chrome watcher started, polling port {self.port}")

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._stop_event.set()
        self._thread.join(timeout=2)
        logger.debug("Chrome watcher stopped")

    def _run(self) -> None:
        """Poll Chrome debug port every 5 seconds."""
        while not self._stop_event.is_set():
            was_available = self.available
            self.available = self._check_chrome()

            # State change - broadcast to SSE clients
            if self.available != was_available:
                if self.available:
                    logger.info(f"Chrome detected on port {self.port}")
                else:
                    logger.info(f"Chrome no longer available on port {self.port}")
                self.service._trigger_broadcast()

            self._stop_event.wait(5)  # 5s poll interval

    def _check_chrome(self) -> bool:
        """Check if Chrome debug port is responding."""
        try:
            with httpx.Client(timeout=1) as client:
                resp = client.get(f"http://127.0.0.1:{self.port}/json/version")
                return resp.status_code == 200
        except Exception:
            return False

    def to_dict(self) -> dict:
        """State for SSE broadcast."""
        return {
            "available": self.available,
            "port": self.port,
        }


__all__ = ["ChromeWatcher"]
