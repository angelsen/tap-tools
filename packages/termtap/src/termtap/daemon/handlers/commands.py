"""Command execution RPC handlers.

Handlers for execute and check_ready RPC methods.
"""

import logging

from ...pane import Pane
from ..context import DaemonContext

logger = logging.getLogger(__name__)

__all__ = ["register_handlers"]


def register_handlers(rpc, ctx: DaemonContext):
    """Register command execution handlers.

    Args:
        rpc: RPCDispatcher instance
        ctx: DaemonContext with daemon dependencies
    """

    @rpc.method("execute")
    async def _execute(target: str, command: str, client_context: dict):
        """Execute command with live pattern matching.

        Flow:
        1. Pre-check pattern state
        2. If ready: mark, paste command, create WATCHING action
        3. If busy: return busy status
        4. If unknown: return READY_CHECK action for UI

        Args:
            target: Target pane identifier
            command: Command to execute
            client_context: Client context (pane, session) from environment
        """
        from ..queue import ActionState
        from .helpers import begin_watching, resolve_pane_target

        pane_id, err = resolve_pane_target(target)
        if err:
            return err
        assert pane_id is not None

        # Check if trying to execute in client's active pane
        client_pane = client_context.get("pane", "")
        if client_pane and pane_id == client_pane:
            return {"status": "error", "error": "Cannot execute in your active pane"}

        ctx.pane_manager.ensure_pipe_pane(pane_id)
        pane = ctx.pane_manager.get_or_create(pane_id)

        # Pre-check: pattern match current state with info about which pattern matched
        pane_capture = Pane.get(pane_id, pane, n=10)
        pane.process = pane_capture.process
        state, matched_pattern = ctx.patterns.match_with_info(pane_capture.process, pane_capture.content)

        logger.debug(
            f"Execute pre-check: pane={pane_id} process={pane.process} state={state or 'unknown'} pattern={matched_pattern}"
        )

        if state == "ready":
            action = ctx.queue.add(
                pane_id=pane_id,
                command=command,
                state=ActionState.WATCHING,
                client_context=client_context,
            )
            action.matched_ready_pattern = matched_pattern

            # Check if this ready pattern is part of a pair
            if matched_pattern:
                pair = ctx.patterns.get_pair_for_ready(pane.process, matched_pattern)
                if pair and pair.busy:
                    action.pair_mode = True
                    action.linked_busy_pattern = pair.busy
                    logger.info(f"Action {action.id}: auto-enabled pair mode with busy={pair.busy}")

            begin_watching(ctx.pane_manager, action)

            logger.info(f"Action {action.id} created: pane={pane_id} cmd={command[:50]} state=WATCHING")

            await ctx.daemon.broadcast_event({"type": "action_added", "action": action.to_dict()})

            return {"status": "watching", "action_id": action.id}

        elif state == "busy":
            # Terminal is busy - capture current output
            logger.debug(f"Execute busy: pane={pane_id}")
            output = Pane.get(pane_id, pane).content
            return {"status": "busy", "output": output}

        else:
            # Unknown state - needs user pattern
            action = ctx.queue.add(
                pane_id=pane_id,
                command=command,
                state=ActionState.READY_CHECK,
                client_context=client_context,
            )
            pane.action = action  # Assign so manager can auto-resolve if pattern matches later

            logger.info(f"Action {action.id} created: pane={pane_id} cmd={command[:50]} state=READY_CHECK")

            await ctx.daemon.broadcast_event({"type": "action_added", "action": action.to_dict()})

            return {"status": "ready_check", "action_id": action.id}

    @rpc.method("check_ready")
    async def _check_ready(target: str):
        """Check if pane is ready for input."""
        from .helpers import resolve_pane_target

        pane_id, err = resolve_pane_target(target)
        if err:
            return err
        assert pane_id is not None

        pane = ctx.pane_manager.get_or_create(pane_id)
        state = pane.check_patterns(ctx.patterns)

        if state == "ready":
            return {"status": "ready"}
        elif state == "busy":
            output = Pane.get(pane_id, pane).content
            return {"status": "busy", "output": output}
        else:
            return {"status": "unknown"}
