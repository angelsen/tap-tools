"""Input simulation service using CDP Input domain.

PUBLIC API:
  - InputService: Element resolution, click, and keystroke simulation
"""

import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

# Special key definitions: name -> (key, code, keyCode, char_text)
# char_text is the text for the intermediate 'char' event (keypress), or None for non-printable keys
_SPECIAL_KEYS: dict[str, tuple[str, str, int, str | None]] = {
    "Enter": ("Enter", "Enter", 13, "\r"),
    "Tab": ("Tab", "Tab", 9, "\t"),
    "Escape": ("Escape", "Escape", 27, None),
    "Backspace": ("Backspace", "Backspace", 8, None),
    "Delete": ("Delete", "Delete", 46, None),
    "ArrowUp": ("ArrowUp", "ArrowUp", 38, None),
    "ArrowDown": ("ArrowDown", "ArrowDown", 40, None),
    "ArrowLeft": ("ArrowLeft", "ArrowLeft", 37, None),
    "ArrowRight": ("ArrowRight", "ArrowRight", 39, None),
    "Home": ("Home", "Home", 36, None),
    "End": ("End", "End", 35, None),
    "PageUp": ("PageUp", "PageUp", 33, None),
    "PageDown": ("PageDown", "PageDown", 34, None),
    "Space": (" ", "Space", 32, " "),
}

_SPECIAL_KEY_RE = re.compile(r"\{(\w+)\}")


def _tokenize_input(text: str) -> list[str]:
    """Split text into characters and {SpecialKey} tokens.

    Returns list where each element is either a single character
    or a special key name (e.g., "Enter", "Tab").

    Raises:
        ValueError: If an unrecognized {Key} sequence is found.
    """
    tokens: list[str] = []
    pos = 0
    for match in _SPECIAL_KEY_RE.finditer(text):
        # Add characters before this match
        for char in text[pos : match.start()]:
            tokens.append(char)
        key_name = match.group(1)
        if key_name not in _SPECIAL_KEYS:
            available = ", ".join(sorted(_SPECIAL_KEYS.keys()))
            raise ValueError(f"Unknown special key: {{{key_name}}}. Available: {available}")
        tokens.append(key_name)
        pos = match.end()
    # Add remaining characters
    for char in text[pos:]:
        tokens.append(char)
    return tokens


class InputService:
    """Element resolution and input simulation via CDP Input domain.

    Provides CSS selector resolution to coordinates, mouse click dispatch,
    and keystroke dispatch for automated browser interaction.

    Attributes:
        service: WebTapService reference for target resolution.
    """

    def __init__(self):
        """Initialize input service."""
        self.service: "Any" = None

    def set_service(self, service: "Any") -> None:
        """Set service reference."""
        self.service = service

    def resolve_element_center(self, cdp: "Any", selector: str) -> tuple[float, float]:
        """Resolve CSS selector to element center coordinates.

        Uses DOM.getDocument -> DOM.querySelector -> DOM.getBoxModel to find
        the center of the element's content box.

        Args:
            cdp: CDPSession instance.
            selector: CSS selector string.

        Returns:
            Tuple of (x, y) center coordinates.

        Raises:
            RPCError: If element not found or has zero-area bounding box.
        """
        doc = cdp.execute("DOM.getDocument", {"depth": 0})
        root_node_id = doc["root"]["nodeId"]

        result = cdp.execute("DOM.querySelector", {"nodeId": root_node_id, "selector": selector})
        node_id = result.get("nodeId", 0)
        if node_id == 0:
            raise ValueError(f"Element not found: {selector}")

        try:
            box = cdp.execute("DOM.getBoxModel", {"nodeId": node_id})
        except RuntimeError as e:
            raise ValueError(f"Element not visible: {selector} ({e})")

        quad = box["model"]["content"]
        # quad is [x1, y1, x2, y2, x3, y3, x4, y4]
        xs = [quad[i] for i in range(0, 8, 2)]
        ys = [quad[i] for i in range(1, 8, 2)]
        x = sum(xs) / 4
        y = sum(ys) / 4

        if max(xs) - min(xs) == 0 or max(ys) - min(ys) == 0:
            raise ValueError(f"Element has zero area: {selector}")

        return x, y

    def click_at(self, cdp: "Any", x: float, y: float) -> None:
        """Dispatch mouse click at coordinates.

        Sends mousePressed followed by mouseReleased.

        Args:
            cdp: CDPSession instance.
            x: X coordinate.
            y: Y coordinate.
        """
        cdp.execute(
            "Input.dispatchMouseEvent",
            {
                "type": "mousePressed",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )
        cdp.execute(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )

    def type_text(self, cdp: "Any", text: str, delay_ms: int = 50) -> None:
        """Type text via CDP Input.dispatchKeyEvent.

        Regular characters are sent as 'char' events. Special keys use
        {KeyName} syntax and are sent as keyDown/keyUp pairs.

        Supported special keys: Enter, Tab, Escape, Backspace, Delete,
        ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Home, End, PageUp,
        PageDown, Space.

        Args:
            cdp: CDPSession instance.
            text: Text to type. Use {Enter}, {Tab}, etc. for special keys.
            delay_ms: Delay between keystrokes in milliseconds.
        """
        delay_s = delay_ms / 1000
        for token in _tokenize_input(text):
            if token in _SPECIAL_KEYS:
                key, code, key_code, char_text = _SPECIAL_KEYS[token]
                cdp.execute(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "key": key,
                        "code": code,
                        "windowsVirtualKeyCode": key_code,
                    },
                )
                # Emit char event (keypress) for keys that produce characters
                if char_text is not None:
                    cdp.execute("Input.dispatchKeyEvent", {"type": "char", "text": char_text})
                cdp.execute(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyUp",
                        "key": key,
                        "code": code,
                        "windowsVirtualKeyCode": key_code,
                    },
                )
            else:
                cdp.execute("Input.dispatchKeyEvent", {"type": "char", "text": token})
            if delay_s > 0:
                time.sleep(delay_s)

    def focus_element(self, cdp: "Any", selector: str) -> None:
        """Focus element via DOM.focus.

        Args:
            cdp: CDPSession instance.
            selector: CSS selector string.

        Raises:
            RPCError: If element not found.
        """
        doc = cdp.execute("DOM.getDocument", {"depth": 0})
        root_node_id = doc["root"]["nodeId"]

        result = cdp.execute("DOM.querySelector", {"nodeId": root_node_id, "selector": selector})
        node_id = result.get("nodeId", 0)
        if node_id == 0:
            raise ValueError(f"Element not found: {selector}")

        cdp.execute("DOM.focus", {"nodeId": node_id})
