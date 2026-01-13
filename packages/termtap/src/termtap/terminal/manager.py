"""Manager for all pane terminals with stream routing.

PUBLIC API:
  - PaneManager: Manages all PaneTerminals and routes stream data
"""

import logging
from collections.abc import Callable

from ..daemon.queue import Action, ActionState
from ..handler.patterns import PatternStore
from .pane_terminal import PaneTerminal

logger = logging.getLogger(__name__)


class PaneManager:
    """Manages all PaneTerminals and routes stream data.

    Responsibilities:
    - Create and cache PaneTerminal instances
    - Route stream data to correct pane
    - Check patterns after each feed
    - Auto-resolve actions when "ready" pattern matches
    """

    def __init__(
        self,
        patterns: PatternStore,
        on_resolve: Callable[[Action], None] | None = None,
        max_lines: int = 5000,
    ):
        """Initialize PaneManager.

        Args:
            patterns: Pattern store for state detection
            on_resolve: Callback when action auto-resolves (optional)
            max_lines: Maximum lines per pane's ring buffer
        """
        self.panes: dict[str, PaneTerminal] = {}
        self.patterns = patterns
        self.on_resolve = on_resolve
        self.max_lines = max_lines
        self._active_pipes: set[str] = set()

    def get_or_create(self, pane_id: str) -> PaneTerminal:
        """Get existing pane or create new one.

        Args:
            pane_id: Pane identifier (e.g., "%123")

        Returns:
            PaneTerminal for this pane
        """
        if pane_id not in self.panes:
            self.panes[pane_id] = PaneTerminal.create(pane_id, max_lines=self.max_lines)
        return self.panes[pane_id]

    def feed(self, pane_id: str, data: bytes) -> None:
        """Feed stream data to pane and check for auto-resolution.

        Args:
            pane_id: Pane identifier
            data: Raw bytes from tmux pipe-pane

        After feeding data, checks patterns for auto-resolution.
        State transitions:
        - READY_CHECK + "ready" match → signal auto-transition (daemon sends command)
        - WATCHING + "ready" match → capture output, complete action
        """
        pane = self.get_or_create(pane_id)
        logger.debug(f"Pane {pane_id} received {len(data)} bytes (total: {pane.bytes_fed + len(data)})")
        pane.feed(data)

        # Track data received since WATCHING started
        if pane.action and pane.action.state == ActionState.WATCHING:
            pane.bytes_since_watching += len(data)

        # Check for auto-resolution based on action state
        if pane.action:
            # check_patterns auto-resolves process if needed
            state = pane.check_patterns(self.patterns)

            logger.debug(f"Pane {pane_id} post-feed check: action={pane.action.id} state={state or 'unknown'} bytes_since_watching={pane.bytes_since_watching}")

            # WATCHING: only auto-resolve if we've received new data since transition
            # (prevents resolving immediately when old prompt is still visible)
            if pane.action.state == ActionState.WATCHING and state == "ready" and pane.bytes_since_watching > 0:
                # WATCHING: capture output since mark and complete
                output = pane.screen.all_content()
                truncated = False  # Screen was cleared on WATCHING start
                logger.info(f"Action {pane.action.id} completed: output={len(output)} chars truncated={truncated}")
                pane.action.result = {"output": output, "truncated": truncated}
                pane.action.state = ActionState.COMPLETED

                if self.on_resolve:
                    self.on_resolve(pane.action)

                pane.action = None

            elif pane.action.state == ActionState.READY_CHECK and state == "ready":
                # READY_CHECK: pattern now matches, signal ready for auto-transition
                logger.info(f"Action {pane.action.id} auto-resolved: pattern matched")
                pane.action.result = {"state": "ready", "auto": True}
                # Don't change state here - daemon will transition to WATCHING

                if self.on_resolve:
                    self.on_resolve(pane.action)

                # Don't clear pane.action - daemon will update it to WATCHING

    def ensure_pipe_pane(self, pane_id: str) -> bool:
        """Ensure tmux pipe-pane is active for this pane.

        Args:
            pane_id: Pane identifier

        Returns:
            True if pipe-pane is active, False on failure
        """
        # Even if we think it's active, verify the pane still exists
        if pane_id in self._active_pipes:
            from ..tmux.ops import get_pane
            if get_pane(pane_id):
                return True
            # Pane is gone, remove from tracking
            self._active_pipes.discard(pane_id)

        import sys
        from ..tmux.core import run_tmux

        cmd = f"{sys.executable} -m termtap.daemon.collector {pane_id}"
        code, _, _ = run_tmux(["pipe-pane", "-t", pane_id, cmd])
        if code == 0:
            self._active_pipes.add(pane_id)
            logger.info(f"Started pipe-pane collector for {pane_id}")
            return True
        logger.error(f"Failed to start pipe-pane for {pane_id}")
        return False

    def stop_pipe_pane(self, pane_id: str) -> None:
        """Stop tmux pipe-pane for this pane.

        Args:
            pane_id: Pane identifier
        """
        if pane_id not in self._active_pipes:
            return
        from ..tmux.core import run_tmux

        run_tmux(["pipe-pane", "-t", pane_id])  # Empty stops it
        self._active_pipes.discard(pane_id)

    def cleanup(self, pane_id: str) -> None:
        """Remove pane terminal.

        Args:
            pane_id: Pane identifier to cleanup

        Removes the pane from cache, freeing resources.
        """
        if pane_id in self.panes:
            del self.panes[pane_id]

    def cleanup_dead(self) -> list[str]:
        """Cleanup panes that no longer exist in tmux.

        Returns:
            List of pane IDs that were removed
        """
        from ..tmux.ops import list_panes

        live_panes = {p.pane_id for p in list_panes()}
        dead = []
        for pane_id in list(self.panes.keys()):
            if pane_id not in live_panes:
                self.cleanup(pane_id)
                self._active_pipes.discard(pane_id)
                dead.append(pane_id)
        return dead


__all__ = ["PaneManager"]
