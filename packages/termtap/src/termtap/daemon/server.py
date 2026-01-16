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
from .queue import ActionQueue, ActionState
from .rpc import RPCDispatcher

__all__ = ["TermtapDaemon"]

logger = logging.getLogger(__name__)

# Popup spawn delays per action state (seconds)
# Allows fast auto-resolution before showing popup
POPUP_DELAYS = {
    ActionState.READY_CHECK: 2.0,  # Pattern learning might auto-resolve
    ActionState.WATCHING: 2.0,  # Command running, might complete fast
    ActionState.SELECTING_PANE: 0.0,  # User interaction required immediately
}


# Import helpers from context module


class TermtapDaemon:
    """Main daemon process managing streams, patterns, and interactions."""

    def __init__(self):
        self.rpc = RPCDispatcher()
        self.event_clients: list[StreamWriter] = []
        self.companion_windows: dict[str, StreamWriter] = {}  # window_id -> writer
        self.master_companion: StreamWriter | None = None
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
            on_hook_fire=self._handle_hook_fire,
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
                self.broadcast_event({"type": "action_watching", "id": action.id, "action": action.to_dict()})
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

    def _handle_hook_fire(self, pane_id: str, hook, output: str):
        """Execute hook action.

        Args:
            pane_id: Pane identifier
            hook: Hook instance that fired
            output: Output that triggered the hook
        """
        from ..tmux.ops import send_keys

        if hook.action == "send_keys" and hook.keys:
            logger.info(f"Hook sending keys to {pane_id}: {hook.keys}")
            for key in hook.keys:
                send_keys(pane_id, key, line_ending="")

    def _register_handlers(self):
        """Register RPC method handlers."""
        from .context import DaemonContext
        from .handlers import register_all_handlers

        ctx = DaemonContext(
            daemon=self,
            queue=self.queue,
            patterns=self.patterns,
            pane_manager=self.pane_manager,
        )

        register_all_handlers(self.rpc, ctx)

    def _ensure_companion_running(self, client_context: dict | None = None):
        """Launch companion popup in client's window.

        Only spawns if master companion exists or window has companion.
        Uses -c flag to target the correct tmux client for popup display.

        Args:
            client_context: Client context with window and client for targeting.
        """
        if not client_context:
            return

        # Master companion handles all windows
        if self.master_companion:
            return

        window = client_context.get("window")
        if not window:
            return

        # Check if companion already running in this window
        if window in self.companion_windows:
            return

        import subprocess
        import sys

        cmd = ["tmux", "display-popup", "-E", "-w", "80%", "-h", "60%"]

        # Target the client directly with -c flag
        if client_context.get("client"):
            cmd.extend(["-c", client_context["client"]])

        cmd.extend([sys.executable, "-m", "termtap", "companion", "--popup"])

        subprocess.Popen(cmd)
        # Don't block - companion will load queue when it connects

    async def _delayed_popup(self, action_id: str, client_context: dict, delay: float):
        """Spawn popup after delay if action still pending."""
        if delay > 0:
            await asyncio.sleep(delay)

        # Check if action still needs user interaction
        if self.queue:
            action = self.queue.get(action_id)
            if action and action.state in (ActionState.READY_CHECK, ActionState.SELECTING_PANE):
                self._ensure_companion_running(client_context)

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
        """Handle event listener connection.

        Expects companion to send handshake with either:
        - {"type": "hello", "master": true} for global companion
        - {"type": "hello", "context": {...}} for window-specific companion
        """
        self.event_clients.append(writer)
        window_id: str | None = None
        is_master: bool = False

        try:
            # Wait for handshake (with timeout)
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=2.0)
                if line:
                    handshake = json.loads(line.decode())
                    if handshake.get("type") == "hello":
                        # Check for master mode
                        if handshake.get("master"):
                            is_master = True
                            self.master_companion = writer
                            logger.info("Master companion registered")
                        # Otherwise check for context with window
                        else:
                            context = handshake.get("context", {})
                            window_id = context.get("window")
                            if window_id:
                                self.companion_windows[window_id] = writer
                                logger.info(f"Companion registered for window {window_id}")
            except (asyncio.TimeoutError, json.JSONDecodeError, KeyError):
                logger.warning("Companion connected without valid handshake")

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
            if is_master and self.master_companion == writer:
                self.master_companion = None
                logger.info("Master companion unregistered")
            if window_id and window_id in self.companion_windows:
                del self.companion_windows[window_id]
                logger.info(f"Companion unregistered from window {window_id}")
            writer.close()
            await writer.wait_closed()

    async def broadcast_event(self, event: dict):
        """Broadcast event to all connected event listeners."""
        # Ensure companion is running when action needs user interaction
        if event.get("type") == "action_added":
            action_data = event.get("action", {})
            client_context = action_data.get("client_context", {})
            action_id = action_data.get("id")
            state_str = action_data.get("state", "")

            # Get delay based on action state
            try:
                state = ActionState(state_str)
                delay = POPUP_DELAYS.get(state, 0.0)
            except ValueError:
                delay = 0.0

            asyncio.create_task(self._delayed_popup(action_id, client_context, delay))

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
