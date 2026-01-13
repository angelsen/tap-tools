"""Termtap daemon server.

PUBLIC API:
  - TermtapDaemon: Main daemon class with async socket servers
"""

import asyncio
import json
import logging
import signal
from asyncio import StreamReader, StreamWriter

from ..handler.patterns import PatternStore
from ..paths import SOCKET_PATH, EVENTS_SOCKET_PATH, COLLECTOR_SOCK_PATH
from ..terminal.manager import PaneManager
from .queue import ActionQueue
from .rpc import RPCDispatcher

__all__ = ["TermtapDaemon"]

logger = logging.getLogger(__name__)


def _format_queue_state(queue) -> dict:
    """Format queue state for debug output."""
    import time
    now = time.time()

    return {
        "pending": [
            {
                "id": a.id,
                "pane_id": a.pane_id,
                "command": a.command[:50],
                "state": a.state.value,
                "age_seconds": now - a.timestamp,
            }
            for a in queue.pending
        ],
        "resolved_count": len(queue.resolved),
        "utilization": len(queue.pending) / queue.max_size,
    }


def _format_panes_state(manager) -> dict:
    """Format pane manager state for debug output."""
    import time
    now = time.time()

    result = {}
    for pane_id, pane in manager.panes.items():
        action_info = None
        if pane.action:
            action_info = {
                "id": pane.action.id,
                "state": pane.action.state.value,
                "age_seconds": now - pane.action.timestamp,
            }

        result[pane_id] = {
            "process": pane.process,
            "collecting": pane_id in manager._active_pipes,
            "bytes_fed": pane.bytes_fed,
            "action": action_info,
            "buffer": {
                "line_count": pane.screen.line_count,
                "base_idx": pane.screen.base_idx,
                "mark_idx": pane.screen.mark_idx,
                "preserve_before": pane.screen.preserve_before,
            },
        }

    return result


def _format_patterns_state(patterns) -> dict:
    """Format pattern store state for debug output."""
    process_counts = {}
    for process, states in patterns.patterns.items():
        counts = {state: len(plist) for state, plist in states.items()}
        process_counts[process] = counts

    return {
        "path": str(patterns.path),
        "processes": process_counts,
        "total_patterns": sum(
            len(plist)
            for states in patterns.patterns.values()
            for plist in states.values()
        ),
    }


def _make_serializable(obj):
    """Convert non-JSON types to serializable format."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, set):
        return list(obj)
    # For other types, use repr
    return repr(obj)


class TermtapDaemon:
    """Main daemon process managing streams, patterns, and interactions."""

    def __init__(self):
        self.rpc = RPCDispatcher()
        self.event_clients: list[StreamWriter] = []
        self._running = False
        self._servers: list[asyncio.Server] = []
        self._log_buffer: list[str] = []  # Ring buffer for recent logs

        self.pane_manager: PaneManager | None = None
        self.queue: ActionQueue | None = None
        self.patterns: PatternStore | None = None

        self._setup_log_handler()

    def _setup_components(self):
        """Initialize components."""
        self.queue = ActionQueue()
        self.patterns = PatternStore()

        # Create PaneManager with auto-resolution callback
        self.pane_manager = PaneManager(
            patterns=self.patterns,
            on_resolve=self._handle_auto_resolve,
        )

        self._register_handlers()

    def _setup_log_handler(self):
        """Add handler to capture logs in memory."""
        class BufferHandler(logging.Handler):
            def __init__(self, buffer: list[str]):
                super().__init__()
                self.buffer = buffer

            def emit(self, record):
                msg = f"[{record.levelname}] {record.name}: {record.getMessage()}"
                self.buffer.append(msg)
                if len(self.buffer) > 500:  # Keep last 500
                    self.buffer.pop(0)

        handler = BufferHandler(self._log_buffer)
        handler.setLevel(logging.DEBUG)

        # Set logger level to DEBUG so messages reach the handler
        termtap_logger = logging.getLogger("termtap")
        termtap_logger.setLevel(logging.DEBUG)
        termtap_logger.addHandler(handler)

    def _handle_auto_resolve(self, action):
        """Handle auto-resolved action from PaneManager.

        Called when pattern matching auto-resolves an action.
        For READY_CHECK: sends command and transitions to WATCHING.
        For WATCHING: removes from queue and broadcasts completion.
        """
        from .queue import ActionState

        # READY_CHECK auto-resolve: send command, transition to WATCHING
        if action.result and action.result.get("auto") and action.state == ActionState.READY_CHECK:
            from ..tmux.ops import send_keys

            if not self.pane_manager:
                return

            pane = self.pane_manager.get_or_create(action.pane_id)
            pane.screen.clear()
            send_keys(action.pane_id, action.command)

            # Transition to WATCHING
            action.state = ActionState.WATCHING
            action.result = None  # Clear the auto flag
            pane.action = action
            pane.bytes_since_watching = 0  # Reset counter for new data tracking

            asyncio.create_task(
                self.broadcast_event(
                    {"type": "action_watching", "id": action.id, "action": action.to_dict()}
                )
            )
            return

        # WATCHING completion: remove from queue and broadcast
        if self.queue:
            self.queue.resolve(action.id, action.result or {})

        asyncio.create_task(
            self.broadcast_event(
                {
                    "type": "action_resolved",
                    "id": action.id,
                    "output": action.result.get("output", "") if action.result else "",
                    "truncated": action.result.get("truncated", False) if action.result else False,
                }
            )
        )

    def _register_handlers(self):
        """Register RPC method handlers."""
        assert self.queue is not None
        assert self.patterns is not None
        assert self.pane_manager is not None

        queue = self.queue
        patterns = self.patterns
        pane_manager = self.pane_manager

        @self.rpc.method("execute")
        async def execute(target: str, command: str, client_pane: str):
            """Execute command with live pattern matching.

            Flow:
            1. Pre-check pattern state
            2. If ready: mark, send_keys, create WATCHING action
            3. If busy: return busy status
            4. If unknown: return READY_CHECK action for UI

            Args:
                target: Target pane identifier
                command: Command to execute
                client_pane: Client's active pane from $TMUX_PANE (use "" if not in tmux)
            """
            from ..tmux.ops import send_keys, resolve_pane_id
            from .queue import ActionState

            # Resolve pane ID
            pane_id = resolve_pane_id(target)
            if not pane_id:
                return {"status": "error", "error": f"Pane not found: {target}"}

            # Check if trying to execute in client's active pane
            if client_pane and pane_id == client_pane:
                return {"status": "error", "error": "Cannot execute in your active pane"}

            # Ensure pipe-pane is active
            pane_manager.ensure_pipe_pane(pane_id)

            # Get or create pane terminal
            pane = pane_manager.get_or_create(pane_id)

            # Pre-check: pattern match current state
            # check_patterns handles both empty stream (tmux capture) and stream buffer
            state = pane.check_patterns(patterns)

            logger.debug(f"Execute pre-check: pane={pane_id} process={pane.process} state={state or 'unknown'}")

            if state == "ready":
                # Clear stream, send command, create WATCHING action
                pane.screen.clear()
                send_keys(pane_id, command)

                action = queue.add(
                    pane_id=pane_id,
                    command=command,
                    state=ActionState.WATCHING,
                )
                pane.action = action

                logger.info(f"Action {action.id} created: pane={pane_id} cmd={command[:50]} state=WATCHING")

                await self.broadcast_event({"type": "action_added", "action": action.to_dict()})

                return {"status": "watching", "action_id": action.id}

            elif state == "busy":
                # Terminal is busy
                logger.debug(f"Execute busy: pane={pane_id}")
                return {"status": "busy"}

            else:
                # Unknown state - needs user pattern
                action = queue.add(
                    pane_id=pane_id,
                    command=command,
                    state=ActionState.READY_CHECK,
                )
                pane.action = action  # Assign so manager can auto-resolve if pattern matches later

                logger.info(f"Action {action.id} created: pane={pane_id} cmd={command[:50]} state=READY_CHECK")

                await self.broadcast_event({"type": "action_added", "action": action.to_dict()})

                return {"status": "ready_check", "action_id": action.id}

        @self.rpc.method("send")
        async def send(target: str, message: str):
            """Send message (alias for execute)."""
            return await execute(target, message)

        @self.rpc.method("check_ready")
        async def check_ready(target: str):
            """Check if pane is ready for input."""
            from ..tmux.ops import resolve_pane_id

            pane_id = resolve_pane_id(target)
            if not pane_id:
                return {"status": "error", "error": f"Pane not found: {target}"}

            pane = pane_manager.get_or_create(pane_id)
            state = pane.check_patterns(patterns)

            if state == "ready":
                return {"status": "ready"}
            elif state == "busy":
                return {"status": "busy"}
            else:
                return {"status": "unknown"}


        @self.rpc.method("resolve")
        async def resolve(action_id: str, result: dict[str, str]):
            """Resolve action with user response.

            Handles state transitions:
            - READY_CHECK + ready: mark stream, send command, transition to WATCHING
            - WATCHING + ready: capture output since mark, complete action
            - Otherwise: just resolve as-is
            """
            from ..tmux.ops import send_keys
            from .queue import ActionState

            action = queue.get(action_id)
            if not action:
                return {"ok": False, "error": "Action not found"}

            # Handle READY_CHECK → WATCHING transition
            if action.state == ActionState.READY_CHECK and result.get("state") == "ready":
                pane = pane_manager.get_or_create(action.pane_id)
                pane.screen.clear()
                send_keys(action.pane_id, action.command)

                # Transition to WATCHING
                action.state = ActionState.WATCHING
                pane.action = action
                pane.bytes_since_watching = 0  # Reset counter for new data tracking

                await self.broadcast_event({"type": "action_watching", "id": action_id, "action": action.to_dict()})
                return {"ok": True, "status": "watching"}

            # Handle WATCHING completion
            if action.state == ActionState.WATCHING and result.get("state") == "ready":
                pane = pane_manager.get_or_create(action.pane_id)
                output = pane.screen.all_content()

                action.result = {"output": output, "truncated": False, "state": "ready"}
                queue.resolve(action_id, action.result)

                await self.broadcast_event({"type": "action_resolved", "id": action_id})
                return {"ok": True, "status": "completed", "result": action.result}

            # Handle SELECTING_PANE resolution (pane selected by user)
            if action.state == ActionState.SELECTING_PANE:
                selected_pane = result.get("pane_id") or result.get("panes")
                if selected_pane:
                    # Complete the selection
                    queue.resolve(action_id, result)
                    await self.broadcast_event({"type": "action_resolved", "id": action_id})
                    return {"ok": True, "status": "completed", "result": result}

            # Default: just resolve
            queue.resolve(action_id, result)
            await self.broadcast_event({"type": "action_resolved", "id": action_id})
            return {"ok": True}

        @self.rpc.method("get_queue")
        async def get_queue():
            return {"actions": queue.to_dict()}

        @self.rpc.method("get_status")
        async def get_status(action_id: str):
            from .queue import ActionState

            action = queue.get(action_id)
            if not action:
                return {"status": "not_found"}
            if action.state == ActionState.COMPLETED:
                return {"status": "completed", "result": action.result}
            if action.state == ActionState.CANCELLED:
                return {"status": "cancelled", "result": action.result}
            if action.state == ActionState.WATCHING:
                return {"status": "watching"}
            if action.state == ActionState.READY_CHECK:
                return {"status": "ready_check"}
            if action.state == ActionState.SELECTING_PANE:
                return {"status": "selecting_pane"}
            return {"status": "unknown"}

        @self.rpc.method("learn_pattern")
        async def learn_pattern(process: str, pattern: str, state: str):
            patterns.add(process, pattern, state)
            return {"ok": True}

        @self.rpc.method("get_patterns")
        async def get_patterns(process: str | None = None):
            if process:
                return {"patterns": patterns.get(process)}
            return {"patterns": patterns.all()}

        @self.rpc.method("remove_pattern")
        async def remove_pattern(process: str, pattern: str, state: str):
            patterns.remove(process, pattern, state)
            return {"ok": True}

        @self.rpc.method("interrupt")
        async def interrupt(target: str):
            from ..tmux.ops import send_keys

            send_keys(target, "C-c")
            return {"status": "sent"}

        @self.rpc.method("get_pane_data")
        async def get_pane_data(pane_id: str, lines: int = 20):
            """Get live pane data for display."""
            from ..pane import Pane
            from ..tmux.ops import get_pane

            captured = Pane.capture_tail(pane_id, lines)
            # Get swp from pane info (Pane doesn't include this)
            info = get_pane(pane_id)

            return {
                "content": captured.content,
                "process": captured.process,  # Use Pane's synced process
                "swp": info.swp if info else "",
            }

        @self.rpc.method("ls")
        async def ls():
            from ..tmux.ops import list_panes
            from dataclasses import asdict

            panes = list_panes()
            return {"panes": [asdict(p) for p in panes]}

        @self.rpc.method("cleanup")
        async def cleanup():
            removed = pane_manager.cleanup_dead()
            return {"removed": len(removed)}

        @self.rpc.method("ping")
        async def ping():
            return {"pong": True}

        @self.rpc.method("debug_eval")
        async def debug_eval(code: str):
            """Execute Python code with daemon state context.

            Args:
                code: Python expression/statement to execute

            Returns:
                dict with result, logs (if any), error (if any)
            """
            from types import SimpleNamespace

            captured = []

            # Build context object
            ctx = SimpleNamespace(
                queue=lambda: _format_queue_state(queue),
                panes=lambda: _format_panes_state(pane_manager),
                patterns=lambda: _format_patterns_state(patterns),
                health=lambda: {
                    "running": self._running,
                    "event_clients": len(self.event_clients),
                    "servers": len(self._servers),
                    "logs_buffered": len(self._log_buffer),
                },
                logs=lambda n=50: self._log_buffer[-n:] if self._log_buffer else [],
                raw=SimpleNamespace(
                    queue=queue,
                    pane_manager=pane_manager,
                    patterns=patterns,
                    daemon=self,
                ),
                log=lambda *args: captured.append(" ".join(str(a) for a in args)),
            )

            try:
                # Use exec() for statements, capture result variable if set
                import builtins
                namespace = {"ctx": ctx, "result": None, "__builtins__": builtins}
                exec(code, namespace)
                result = namespace.get("result")

                # Serialize non-JSON types
                result = _make_serializable(result)

                return {
                    "result": result,
                    **({"logs": captured} if captured else {}),
                }
            except Exception as e:
                return {
                    "result": None,
                    "error": str(e),
                    **({"logs": captured} if captured else {}),
                }

        @self.rpc.method("select_pane")
        async def select_pane(command: str):
            from ..tmux.ops import list_panes
            from .queue import ActionState

            panes = list_panes()

            if not panes:
                return {"status": "error", "error": "No panes available"}

            if len(panes) == 1:
                return {"status": "completed", "pane": panes[0].pane_id}

            action = queue.add(
                pane_id="",
                command=command,
                state=ActionState.SELECTING_PANE,
            )

            await self.broadcast_event({"type": "action_added", "action": action.to_dict()})
            return {"status": "selecting_pane", "action_id": action.id}

        @self.rpc.method("select_panes")
        async def select_panes(command: str):
            """Select multiple panes via companion UI."""
            from ..tmux.ops import list_panes
            from .queue import ActionState

            panes = list_panes()
            if not panes:
                return {"status": "error", "error": "No panes available"}

            action = queue.add(
                pane_id="",
                command=command,
                state=ActionState.SELECTING_PANE,
                multi_select=True,
            )

            await self.broadcast_event({"type": "action_added", "action": action.to_dict()})
            return {"status": "selecting_pane", "action_id": action.id}

    def _ensure_companion_running(self):
        """Launch companion in popup if not connected."""
        if self.event_clients:
            return  # Already connected

        import subprocess
        import sys

        subprocess.Popen(
            [
                "tmux",
                "display-popup",
                "-E",
                "-w",
                "80%",
                "-h",
                "60%",
                sys.executable,
                "-m",
                "termtap",
                "companion",
                "--popup",
            ]
        )
        # Don't block - companion will load queue when it connects

    async def start(self):
        """Start daemon and listen on all sockets."""
        self._setup_components()
        self._running = True

        # Clean up old sockets
        for sock_path in [SOCKET_PATH, EVENTS_SOCKET_PATH, COLLECTOR_SOCK_PATH]:
            if sock_path.exists():
                sock_path.unlink()

        # Start RPC server
        rpc_server = await asyncio.start_unix_server(self._handle_rpc, path=str(SOCKET_PATH))
        SOCKET_PATH.chmod(0o600)
        self._servers.append(rpc_server)
        logger.info(f"RPC server listening on {SOCKET_PATH}")

        # Start events server
        events_server = await asyncio.start_unix_server(self._handle_events, path=str(EVENTS_SOCKET_PATH))
        EVENTS_SOCKET_PATH.chmod(0o600)
        self._servers.append(events_server)
        logger.info(f"Events server listening on {EVENTS_SOCKET_PATH}")

        # Start collector server
        collector_server = await asyncio.start_unix_server(self._handle_collector, path=str(COLLECTOR_SOCK_PATH))
        COLLECTOR_SOCK_PATH.chmod(0o600)
        self._servers.append(collector_server)
        logger.info(f"Collector server listening on {COLLECTOR_SOCK_PATH}")

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        logger.info("Daemon started")

    async def stop(self):
        """Gracefully stop the daemon."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping daemon...")

        # Close event clients
        for writer in self.event_clients:
            writer.close()
            await writer.wait_closed()

        # Close servers
        for server in self._servers:
            server.close()
            await server.wait_closed()

        # Clean up sockets
        for sock_path in [SOCKET_PATH, EVENTS_SOCKET_PATH, COLLECTOR_SOCK_PATH]:
            if sock_path.exists():
                sock_path.unlink()

        logger.info("Daemon stopped")

    async def run(self):
        """Start and run until stopped."""
        await self.start()
        while self._running:
            await asyncio.sleep(1)

    async def _handle_collector(self, reader: StreamReader, writer: StreamWriter):
        """Handle incoming collector connection.

        Protocol:
        1. First line is pane_id
        2. Subsequent data is raw output from the pane
        """
        pane_id: str | None = None
        bytes_received = 0
        try:
            # First line is pane_id
            line = await reader.readline()
            if not line:
                logger.warning("Collector connected but sent no pane_id")
                return

            pane_id = line.decode().strip()
            logger.info(f"Collector connected for {pane_id}")

            # Read and route all data to PaneManager
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    logger.info(f"Collector {pane_id} EOF after {bytes_received} bytes")
                    break
                bytes_received += len(chunk)
                if self.pane_manager:
                    self.pane_manager.feed(pane_id, chunk)

        except (ConnectionResetError, BrokenPipeError) as e:
            logger.warning(f"Collector {pane_id} connection error after {bytes_received} bytes: {e}")
        except Exception as e:
            logger.error(f"Collector {pane_id} unexpected error: {e}", exc_info=True)
        finally:
            # Mark pipe as inactive so it can be restarted
            if pane_id and self.pane_manager:
                logger.warning(f"Pipe-pane collector stopped for {pane_id} (total: {bytes_received} bytes)")
                self.pane_manager._active_pipes.discard(pane_id)
                # Clear stale process info so it refreshes on next use
                if pane_id in self.pane_manager.panes:
                    self.pane_manager.panes[pane_id].process = ""

            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_rpc(self, reader: StreamReader, writer: StreamWriter):
        """Handle incoming RPC connection."""
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                response = await self.rpc.dispatch(data)
                writer.write(response)
                await writer.drain()
        except ConnectionResetError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def _handle_events(self, reader: StreamReader, writer: StreamWriter):
        """Handle event listener connection."""
        self.event_clients.append(writer)
        try:
            # Keep connection open until client disconnects
            while True:
                data = await reader.read(1)
                if not data:
                    break
        except ConnectionResetError:
            pass
        finally:
            if writer in self.event_clients:
                self.event_clients.remove(writer)
            writer.close()
            await writer.wait_closed()

    async def broadcast_event(self, event: dict):
        """Broadcast event to all connected event listeners."""
        # Ensure companion is running when action needs user interaction
        if event.get("type") == "action_added":
            self._ensure_companion_running()

        if not self.event_clients:
            return

        data = json.dumps(event).encode() + b"\n"
        dead_clients = []

        for writer in self.event_clients:
            try:
                writer.write(data)
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                dead_clients.append(writer)

        for writer in dead_clients:
            self.event_clients.remove(writer)
