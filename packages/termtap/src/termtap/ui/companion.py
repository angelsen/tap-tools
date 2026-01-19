"""Textual companion app for termtap.

PUBLIC API:
  - TermtapCompanion: Screen-based TUI for action queue and pattern marking
  - run_companion: Entry point for companion app
"""

import asyncio
import json
import socket

from textual.app import App
from textual.timer import Timer

from ..paths import EVENTS_SOCKET_PATH, SOCKET_PATH
from .screens import PaneSelectScreen, PatternScreen, QueueScreen

__all__ = ["TermtapCompanion", "run_companion"]


class TermtapCompanion(App):
    """Screen-based TUI for termtap action queue.

    Uses QueueScreen as home, pushes PaneSelectScreen or PatternScreen for each action.
    Event listener handles action_added and action_resolved events.
    """

    CSS_PATH = "companion.tcss"

    def __init__(self, popup_mode: bool = False, master_mode: bool = False):
        super().__init__()
        self.popup_mode = popup_mode
        self.master_mode = master_mode
        self._event_task: asyncio.Task | None = None
        self._queue_screen: QueueScreen | None = None
        self._exit_timer: Timer | None = None

    def _create_action_screen(self, action: dict):
        """Create appropriate screen for action state."""
        state = action.get("state", "")
        if state == "selecting_pane":
            # Pane selection needed
            return PaneSelectScreen(action, multi_select=action.get("multi_select", False))
        else:
            # Pattern marking (ready_check or watching)
            return PatternScreen(action)

    def on_mount(self) -> None:
        """Initialize with QueueScreen and start event listener."""
        self.title = "Termtap Companion"
        self._queue_screen = QueueScreen()
        self.push_screen(self._queue_screen)
        self._event_task = asyncio.create_task(self._listen_events())
        self.call_after_refresh(self._load_queue)  # Defer to after app ready

    def on_screen_resume(self) -> None:
        """Check for empty queue when returning to queue screen."""
        if self.popup_mode and isinstance(self.screen, QueueScreen):
            if not self._queue_screen or not self._queue_screen.actions:
                self.exit()

    def _load_queue(self) -> None:
        """Load queue from daemon."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(str(SOCKET_PATH))

            request = {"method": "get_queue", "params": {}, "id": 1}
            sock.sendall(json.dumps(request).encode() + b"\n")

            response = json.loads(sock.recv(65536).decode())
            sock.close()

            if "result" in response:
                actions = response["result"].get("actions", [])
                if self._queue_screen:
                    self._queue_screen.set_actions(actions)

                # Auto-open first action if any
                if actions:
                    self.push_screen(self._create_action_screen(actions[-1]))

                # Exit in popup mode if no actions
                if self.popup_mode and not actions:
                    self.exit()
        except Exception:
            pass

    async def _listen_events(self) -> None:
        """Listen for daemon events with reconnection."""
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(str(EVENTS_SOCKET_PATH))

                # Send handshake with context or master flag
                from ..tmux.ops import build_client_context

                if self.master_mode:
                    handshake = {"type": "hello", "master": True}
                else:
                    context = build_client_context()
                    handshake = {"type": "hello", "context": context}

                writer.write(json.dumps(handshake).encode() + b"\n")
                await writer.drain()

                # Queue already loaded in on_mount(), just listen for new events
                while True:
                    line = await reader.readline()
                    if not line:
                        break

                    try:
                        event = json.loads(line.decode())
                        self._handle_event(event)
                    except json.JSONDecodeError:
                        pass

            except (ConnectionRefusedError, FileNotFoundError, OSError):
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                return

    def _handle_event(self, event: dict) -> None:
        """Handle daemon event."""
        event_type = event.get("type")

        if event_type == "queue_updated":
            actions = event.get("queue", [])
            if self._queue_screen:
                self._queue_screen.set_actions(actions)

        elif event_type == "action_added":
            action = event.get("action")
            if action and self._queue_screen:
                # Cancel any pending exit - new action arrived
                if self._exit_timer:
                    self._exit_timer.stop()
                    self._exit_timer = None

                # Update queue
                actions = self._queue_screen.actions + [action]
                self._queue_screen.set_actions(actions)

                # Auto-open if on queue screen
                if isinstance(self.screen, QueueScreen):
                    self.push_screen(self._create_action_screen(action))

        elif event_type == "action_watching":
            action = event.get("action")
            if action and self._queue_screen:
                # Update action in queue (state changed to watching)
                actions = [a if a.get("id") != action.get("id") else action for a in self._queue_screen.actions]
                self._queue_screen.set_actions(actions)

                # If showing this action's screen, pop and push new screen with updated action
                if isinstance(self.screen, (PaneSelectScreen, PatternScreen)):
                    current_action_id = getattr(self.screen, "action", {}).get("id")
                    if current_action_id == action.get("id"):
                        self.pop_screen()
                        self.push_screen(self._create_action_screen(action))

        elif event_type == "action_resolved":
            resolved_id = event.get("id")
            if self._queue_screen:
                # Remove resolved action
                actions = [a for a in self._queue_screen.actions if a.get("id") != resolved_id]
                self._queue_screen.set_actions(actions)

                # If on action screen, pop and open next
                if isinstance(self.screen, (PaneSelectScreen, PatternScreen)):
                    self.pop_screen()
                    if actions:
                        self.push_screen(self._create_action_screen(actions[0]))

                # Delayed exit in popup mode - wait for potential follow-up actions
                if self.popup_mode and not actions:
                    self._exit_timer = self.set_timer(0.6, self._check_and_exit)

        elif event_type == "action_cancelled":
            cancelled_id = event.get("id")
            if self._queue_screen:
                # Remove cancelled action
                actions = [a for a in self._queue_screen.actions if a.get("id") != cancelled_id]
                self._queue_screen.set_actions(actions)

            # Pop screen if we're on the cancelled action's screen
            if isinstance(self.screen, (PaneSelectScreen, PatternScreen)):
                current_action_id = getattr(self.screen, "action", {}).get("id")
                if current_action_id == cancelled_id:
                    self.pop_screen()
                    if self._queue_screen and self._queue_screen.actions:
                        self.push_screen(self._create_action_screen(self._queue_screen.actions[0]))

            # Handle popup mode exit
            if self.popup_mode and self._queue_screen and not self._queue_screen.actions:
                self._exit_timer = self.set_timer(0.6, self._check_and_exit)

    def _check_and_exit(self) -> None:
        """Exit if queue is still empty after delay."""
        self._exit_timer = None
        if self._queue_screen and not self._queue_screen.actions:
            self.exit()

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if self._event_task:
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass


def run_companion(popup_mode: bool = False, master_mode: bool = False) -> None:
    """Run companion app.

    Args:
        popup_mode: If True, auto-dismiss when queue empties
        master_mode: If True, companion is global (not tied to a window)
    """
    app = TermtapCompanion(popup_mode=popup_mode, master_mode=master_mode)
    app.run()
