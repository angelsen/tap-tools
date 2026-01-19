"""Manager for all pane terminals with stream routing.

PUBLIC API:
  - PaneManager: Manages all PaneTerminals and routes stream data
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..daemon.queue import Action, ActionState
from ..handler.patterns import PatternStore
from ..pane import Pane
from .pane_terminal import PaneTerminal

if TYPE_CHECKING:
    from ..handler.hooks import Hook

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
        on_hook_fire: Callable[[str, "Hook", str], None] | None = None,
        max_lines: int = 5000,
    ):
        """Initialize PaneManager.

        Args:
            patterns: Pattern store for state detection
            on_resolve: Callback when action auto-resolves (optional)
            on_hook_fire: Callback when hook fires (optional)
            max_lines: Maximum lines per pane's ring buffer
        """
        self.panes: dict[str, PaneTerminal] = {}
        self.patterns = patterns
        self.on_resolve = on_resolve
        self.on_hook_fire = on_hook_fire
        self.max_lines = max_lines
        self._active_pipes: set[str] = set()
        self._busy_tracking: dict[str, bool] = {}  # action_id -> seen_busy

    def get_or_create(self, pane_id: str) -> PaneTerminal:
        """Get existing pane or create new one.

        Args:
            pane_id: Pane identifier (e.g., "%123")

        Returns:
            PaneTerminal for this pane
        """
        import time

        if pane_id not in self.panes:
            self.panes[pane_id] = PaneTerminal.create(pane_id, max_lines=self.max_lines)
        pane = self.panes[pane_id]
        pane.last_accessed = time.time()
        return pane

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

        # Phase 1: Check state (for action resolution)
        state = pane.check_patterns(self.patterns) if pane.action else None

        # Phase 2: Always check hooks (independent of action state)
        self._check_hooks(pane_id, pane)

        # Phase 3: Handle action based on state
        if pane.action:
            logger.debug(
                f"Pane {pane_id} post-feed check: action={pane.action.id} state={state or 'unknown'} bytes_since_watching={pane.bytes_since_watching}"
            )

            # WATCHING: only auto-resolve if we've received new data since transition
            # (prevents resolving immediately when old prompt is still visible)
            if pane.action.state == ActionState.WATCHING and pane.bytes_since_watching > 0:
                # Distinguish between manual teaching and auto-pair mode
                # Auto-pair: linked_busy_pattern set from start (from execute pre-check)
                # Manual: linked_busy_pattern set later (user presses 'b', completes via RPC)
                is_auto_pair = pane.action.pair_mode and pane.action.linked_busy_pattern is not None

                if is_auto_pair:
                    # Auto-pair mode: wait for busy pattern to appear then disappear
                    from ..handler.patterns import compile_dsl

                    action_id = pane.action.id
                    assert pane.action.linked_busy_pattern is not None  # Guaranteed by is_auto_pair check

                    # Check if busy pattern is currently visible
                    busy_regex = compile_dsl(pane.action.linked_busy_pattern)
                    busy_visible = bool(busy_regex.search(Pane.get(pane.pane_id, pane, n=10).content))

                    if busy_visible:
                        self._busy_tracking[action_id] = True
                        logger.debug(f"Action {action_id}: busy pattern visible")
                    elif self._busy_tracking.get(action_id, False) and state == "ready":
                        # Busy was seen, now gone, ready matches → complete
                        output = Pane.get(pane.pane_id, pane).content
                        truncated = False
                        logger.info(f"Action {action_id} completed (auto-pair): busy disappeared")
                        pane.action.result = {"output": output, "truncated": truncated}
                        pane.action.state = ActionState.COMPLETED

                        if self.on_resolve:
                            self.on_resolve(pane.action)

                        # Cleanup tracking
                        self._busy_tracking.pop(action_id, None)
                        pane.action = None
                elif state == "ready":
                    # Normal mode: complete when ready pattern matches
                    # (Manual teaching completes via set_linked_busy RPC before reaching here)
                    action_id = pane.action.id
                    output = Pane.get(pane.pane_id, pane).content
                    truncated = False
                    logger.info(f"Action {action_id} completed: output={len(output)} chars")
                    pane.action.result = {"output": output, "truncated": truncated}
                    pane.action.state = ActionState.COMPLETED

                    if self.on_resolve:
                        self.on_resolve(pane.action)

                    pane.action = None
                    self._busy_tracking.pop(action_id, None)  # cleanup if exists

            elif pane.action.state == ActionState.READY_CHECK and state == "ready":
                # READY_CHECK: pattern now matches, signal ready for auto-transition
                logger.info(f"Action {pane.action.id} auto-resolved: pattern matched")
                pane.action.result = {"state": "ready", "auto": True}
                # Don't change state here - daemon will transition to WATCHING

                if self.on_resolve:
                    self.on_resolve(pane.action)

                # Don't clear pane.action - daemon will update it to WATCHING

    def _check_hooks(self, pane_id: str, pane: PaneTerminal) -> None:
        """Check and fire matching hooks for pane.

        Args:
            pane_id: Pane identifier
            pane: PaneTerminal instance
        """
        if not pane.process:
            return

        output = Pane.get(pane_id, pane, n=10).content
        if not output:
            return

        matched = self.patterns.hook_manager.check_hooks(pane.process, output)
        for hook in matched:
            logger.info(f"Hook fired: pane={pane_id} pattern={hook.pattern}")
            hook.mark_fired()
            if self.on_hook_fire:
                self.on_hook_fire(pane_id, hook, output)

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
            pane = self.panes[pane_id]
            if pane.action:
                self._busy_tracking.pop(pane.action.id, None)
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
