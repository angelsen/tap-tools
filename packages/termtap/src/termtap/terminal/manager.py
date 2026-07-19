"""Manager for all pane terminals with stream routing.

PUBLIC API:
  - PaneManager: Manages all PaneTerminals and routes stream data
"""

import logging
import sys
import time
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
        self._active_pipes: set[str] = set()  # pipe-pane started in tmux
        self._connected_pipes: set[str] = set()  # collector actually connected back
        self._pipe_started: dict[str, float] = {}  # pane_id -> monotonic start time
        self._busy_seen: set[str] = set()  # action_ids whose busy pattern has appeared

    def get_or_create(self, pane_id: str) -> PaneTerminal:
        """Get existing pane or create new one.

        Args:
            pane_id: Pane identifier (e.g., "%123")

        Returns:
            PaneTerminal for this pane
        """
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
        logger.debug("Pane %s received %d bytes (total: %d)", pane_id, len(data), pane.bytes_fed + len(data))
        pane.feed(data)

        # Track data received since WATCHING started
        if pane.action and pane.action.state == ActionState.WATCHING:
            pane.bytes_since_watching += len(data)

        # Nothing watches this pane: skip the content build entirely
        if not pane.action and not self.patterns.hook_manager.hooks:
            return

        # Build the last-10-lines window once per chunk: pattern check, hooks,
        # and the auto-pair busy check all read the same content.
        recent = Pane.get(pane_id, pane, n=10)
        pane.process = recent.process

        # Phase 1: Check state (for action resolution)
        state = self.patterns.match(recent.process, recent.content) if pane.action else None

        # Phase 2: Always check hooks (independent of action state)
        self._check_hooks(pane_id, recent)

        # Phase 3: Handle action based on state
        if pane.action:
            logger.debug(
                "Pane %s post-feed check: action=%s state=%s bytes_since_watching=%d",
                pane_id,
                pane.action.id,
                state or "unknown",
                pane.bytes_since_watching,
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
                    from ..handler.patterns import dsl_matches, split_output

                    action_id = pane.action.id
                    assert pane.action.linked_busy_pattern is not None  # Guaranteed by is_auto_pair check

                    # Per-line, same semantics as pattern matching everywhere
                    # else — a raw search on the joined window breaks ^/$
                    # anchored patterns.
                    busy_visible = dsl_matches(pane.action.linked_busy_pattern, split_output(recent.content))

                    if busy_visible:
                        self._busy_seen.add(action_id)
                        logger.debug(f"Action {action_id}: busy pattern visible")
                    elif action_id in self._busy_seen and state == "ready":
                        # Busy was seen, now gone, ready matches → complete
                        logger.info(f"Action {action_id} completed (auto-pair): busy disappeared")
                        output = Pane.get(pane.pane_id, pane).content
                        self._finish_watch(pane, action_id, output)
                elif state == "ready":
                    # Normal mode: complete when ready pattern matches
                    # (Manual teaching completes via set_linked_busy RPC before reaching here)
                    action_id = pane.action.id
                    output = Pane.get(pane.pane_id, pane).content
                    logger.info(f"Action {action_id} completed: output={len(output)} chars")
                    self._finish_watch(pane, action_id, output)

            elif pane.action.state == ActionState.READY_CHECK and state == "ready":
                # READY_CHECK: pattern now matches, signal ready for auto-transition
                logger.info(f"Action {pane.action.id} auto-resolved: pattern matched")
                pane.action.result = {"state": "ready", "auto": True}
                # Don't change state here - daemon will transition to WATCHING

                if self.on_resolve:
                    self.on_resolve(pane.action)

                # Don't clear pane.action - daemon will update it to WATCHING

    def _finish_watch(self, pane: PaneTerminal, action_id: str, output: str) -> None:
        """Complete a watched action: set result, notify daemon, detach from pane."""
        assert pane.action is not None
        pane.action.result = {"output": output, "truncated": False}
        pane.action.state = ActionState.COMPLETED

        if self.on_resolve:
            self.on_resolve(pane.action)

        pane.action = None
        self._busy_seen.discard(action_id)

    def _check_hooks(self, pane_id: str, recent: Pane) -> None:
        """Check and fire matching hooks for pane.

        Args:
            pane_id: Pane identifier
            recent: Recent pane content (built once per feed chunk)
        """
        if not recent.process or not recent.content:
            return

        matched = self.patterns.hook_manager.check_hooks(recent.process, recent.content)
        for hook in matched:
            logger.info(f"Hook fired: pane={pane_id} pattern={hook.pattern}")
            hook.mark_fired()
            if self.on_hook_fire:
                self.on_hook_fire(pane_id, hook, recent.content)

    def ensure_pipe_pane(self, pane_id: str) -> bool:
        """Ensure tmux pipe-pane is active for this pane.

        Args:
            pane_id: Pane identifier

        Returns:
            True if pipe-pane is active, False on failure
        """
        # Even if we think it's active, verify the pane still exists and
        # the collector actually connected back (a collector that died at
        # startup would otherwise leave the pane dark forever).
        if pane_id in self._active_pipes:
            from ..tmux.ops import get_pane

            if not get_pane(pane_id):
                # Pane is gone, remove from tracking
                self._active_pipes.discard(pane_id)
            elif pane_id in self._connected_pipes:
                return True
            elif time.monotonic() - self._pipe_started.get(pane_id, 0.0) < 5.0:
                return True  # collector still within startup grace period
            else:
                logger.warning(f"Collector for {pane_id} never connected; restarting pipe")

        from ..tmux.core import run_tmux

        cmd = f"{sys.executable} -m termtap.daemon.collector {pane_id}"
        code, _, _ = run_tmux(["pipe-pane", "-t", pane_id, cmd])
        if code == 0:
            self._active_pipes.add(pane_id)
            self._pipe_started[pane_id] = time.monotonic()
            logger.info(f"Started pipe-pane collector for {pane_id}")
            return True
        logger.error(f"Failed to start pipe-pane for {pane_id}")
        return False

    def cleanup(self, pane_id: str) -> None:
        """Remove pane terminal.

        Args:
            pane_id: Pane identifier to cleanup

        Removes the pane from cache, freeing resources.
        """
        if pane_id in self.panes:
            pane = self.panes[pane_id]
            if pane.action:
                self._busy_seen.discard(pane.action.id)
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
                self._connected_pipes.discard(pane_id)
                self._pipe_started.pop(pane_id, None)
                dead.append(pane_id)
        return dead


__all__ = ["PaneManager"]
