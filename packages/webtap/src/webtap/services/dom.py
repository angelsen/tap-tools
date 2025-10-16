"""DOM inspection service using Chrome DevTools Protocol.

PUBLIC API:
  - DOMService: Manages element inspection and selection via CDP Overlay domain
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from webtap.cdp.session import CDPSession
    from webtap.app import WebTapState

logger = logging.getLogger(__name__)


class DOMService:
    """Manages element inspection and selection via CDP Overlay domain.

    Uses CDP's native inspect mode (Overlay.setInspectMode) which provides:
    - Native Chrome highlight on hover (no custom overlay needed)
    - Click events via Overlay.inspectNodeRequested
    - Accurate element data via DOM.describeNode, CSS.getComputedStyleForNode

    Selections are stored in state.browser_data (not DuckDB) as they are
    ephemeral session data cleared after prompt submission.

    Attributes:
        cdp: CDP session for executing commands
        state: WebTap state for storing selections
        _inspection_active: Whether inspect mode is currently active
        _next_id: Counter for assigning selection IDs
    """

    def __init__(self, cdp: "CDPSession | None" = None, state: "WebTapState | None" = None):
        """Initialize DOM service.

        Args:
            cdp: CDPSession instance. Can be None initially, set via set_cdp().
            state: WebTapState instance. Can be None initially, set via set_state().
        """
        self.cdp = cdp
        self.state = state
        self._inspection_active = False
        self._next_id = 1
        self._broadcast_callback: "Any | None" = None  # Callback to service._trigger_broadcast()
        self._state_lock = threading.Lock()  # Protect state mutations
        self._pending_selections = 0  # Track in-flight selection processing
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dom-worker")

    def set_cdp(self, cdp: "CDPSession") -> None:
        """Set CDP session after initialization."""
        self.cdp = cdp

    def set_state(self, state: "WebTapState") -> None:
        """Set state after initialization."""
        self.state = state

    def set_broadcast_callback(self, callback: "Any") -> None:
        """Set callback for broadcasting state changes.

        Args:
            callback: Function to call when state changes (service._trigger_broadcast)
        """
        self._broadcast_callback = callback

    def start_inspect(self) -> dict[str, Any]:
        """Enable CDP element inspection mode.

        Enables Overlay.setInspectMode with searchForNode mode, which:
        - Shows native Chrome highlight on hover
        - Fires Overlay.inspectNodeRequested on click

        Returns:
            Success status dictionary.
        """
        if not self.cdp or not self.cdp.ws_app:
            return {"error": "Not connected to page"}

        if self._inspection_active:
            return {"error": "Inspection already active"}

        try:
            # Enable DOM domain first (Overlay depends on it)
            self.cdp.execute("DOM.enable")

            # Request document to establish DOM tree context
            # REQUIRED: BackendNodeIds only work after getDocument() is called
            self.cdp.execute("DOM.getDocument", {"depth": -1})

            # Enable CSS domain (needed for computed styles)
            self.cdp.execute("CSS.enable")

            # Enable Overlay domain
            self.cdp.execute("Overlay.enable")

            # Set inspect mode with native Chrome highlighting
            self.cdp.execute(
                "Overlay.setInspectMode",
                {
                    "mode": "searchForNode",
                    "highlightConfig": {
                        "showInfo": True,
                        "showStyles": True,
                        "contentColor": {"r": 111, "g": 168, "b": 220, "a": 0.66},
                        "paddingColor": {"r": 147, "g": 196, "b": 125, "a": 0.55},
                        "borderColor": {"r": 255, "g": 229, "b": 153, "a": 0.66},
                        "marginColor": {"r": 246, "g": 178, "b": 107, "a": 0.66},
                    },
                },
            )

            self._inspection_active = True
            logger.info("Element inspection mode enabled")

            self._trigger_broadcast()
            return {"success": True, "inspect_active": True}

        except Exception as e:
            logger.error(f"Failed to enable inspection mode: {e}")
            return {"error": str(e)}

    def stop_inspect(self) -> dict[str, Any]:
        """Disable CDP element inspection mode.

        Returns:
            Success status dictionary.
        """
        if not self.cdp or not self.cdp.ws_app:
            return {"error": "Not connected to page"}

        if not self._inspection_active:
            return {"success": True, "inspect_active": False}

        try:
            # Disable inspect mode
            # NOTE: highlightConfig required even for mode=none, otherwise CDP throws:
            # "Internal error: highlight configuration parameter is missing"
            self.cdp.execute("Overlay.setInspectMode", {"mode": "none", "highlightConfig": {}})

            self._inspection_active = False
            logger.info("Element inspection mode disabled")

            self._trigger_broadcast()
            return {"success": True, "inspect_active": False}

        except Exception as e:
            logger.error(f"Failed to disable inspection mode: {e}")
            return {"error": str(e)}

    def handle_inspect_node_requested(self, event: dict) -> None:
        """Handle Overlay.inspectNodeRequested event (user clicked element).

        CRITICAL: Called from WebSocket thread - MUST NOT make blocking CDP calls!
        Offload to background thread to avoid deadlock.

        Args:
            event: CDP event with method and params
        """
        if not self.cdp or not self.state:
            logger.error("DOMService not properly initialized (missing cdp or state)")
            return

        params = event.get("params", {})
        backend_node_id = params.get("backendNodeId")
        if not backend_node_id:
            logger.warning("inspectNodeRequested event missing backendNodeId")
            return

        # Increment pending counter (thread-safe)
        with self._state_lock:
            self._pending_selections += 1
        self._trigger_broadcast()

        # Submit to background thread - returns immediately, no blocking
        self._executor.submit(self._process_node_selection, backend_node_id)

    def handle_frame_navigated(self, event: dict) -> None:
        """Handle Page.frameNavigated event (page navigation).

        Clears selections when main frame navigates to keep state in sync with page.
        Called from WebSocket thread - must be non-blocking.

        Args:
            event: CDP event with method and params
        """
        params = event.get("params", {})
        frame = params.get("frame", {})

        # Only clear on main frame navigation (not iframes)
        if frame.get("parentId"):
            return

        logger.info("Main frame navigated - clearing selections")
        self.clear_selections()
        self._trigger_broadcast()

    def _process_node_selection(self, backend_node_id: int) -> None:
        """Process node selection in background thread.

        Safe to make blocking CDP calls here - we're not in WebSocket thread.

        Args:
            backend_node_id: CDP backend node ID from inspectNodeRequested event
        """
        try:
            # Make blocking CDP calls (OK in background thread)
            data = self._extract_node_data(backend_node_id)

            # Thread-safe state update
            with self._state_lock:
                if not self.state:
                    logger.error("DOMService state not initialized")
                    return

                selection_id = str(self._next_id)
                self._next_id += 1

                if not self.state.browser_data:
                    self.state.browser_data = {"selections": {}, "prompt": ""}
                if "selections" not in self.state.browser_data:
                    self.state.browser_data["selections"] = {}

                self.state.browser_data["selections"][selection_id] = data

            logger.info(f"Element selected: {selection_id} - {data.get('preview', {}).get('tag', 'unknown')}")

        except Exception as e:
            logger.error(f"Failed to process node selection: {e}")
            # Set error state for UI display
            if self.state:
                import time

                error_msg = str(e)
                # Provide user-friendly message for common errors
                if "timed out" in error_msg.lower() or isinstance(e, TimeoutError):
                    error_msg = "Element selection timed out - page may be unresponsive"
                self.state.error_state = {"message": error_msg, "timestamp": time.time()}
        finally:
            # Decrement pending counter (thread-safe)
            with self._state_lock:
                self._pending_selections -= 1
            self._trigger_broadcast()

    def _trigger_broadcast(self) -> None:
        """Trigger SSE broadcast via service callback (ensures snapshot update)."""
        if self._broadcast_callback:
            try:
                self._broadcast_callback()
            except Exception as e:
                logger.debug(f"Failed to trigger broadcast: {e}")

    def _extract_node_data(self, backend_node_id: int) -> dict[str, Any]:
        """Extract complete element data via CDP.

        Args:
            backend_node_id: CDP backend node ID from inspectNodeRequested event

        Returns:
            Dictionary with element data compatible with browser_data schema

        Raises:
            RuntimeError: If CDP is not connected or commands fail
            TimeoutError: If CDP commands timeout (page busy, heavy load)
        """
        if not self.cdp:
            raise RuntimeError("CDP session not initialized")

        # Use 15s timeout for interactive operations (balanced between responsiveness and heavy pages)
        # Still shorter than default 30s to provide faster failure feedback
        timeout = 15.0

        try:
            # Describe node directly with backendNodeId (no need for resolveNode first!)
            describe_result = self.cdp.execute("DOM.describeNode", {"backendNodeId": backend_node_id}, timeout=timeout)

            if "node" not in describe_result:
                raise RuntimeError(f"Failed to describe node {backend_node_id}")

            node = describe_result["node"]
            node_id = node["nodeId"]

            # Get outer HTML
            html_result = self.cdp.execute("DOM.getOuterHTML", {"nodeId": node_id}, timeout=timeout)
            outer_html = html_result.get("outerHTML", "")

            # Get computed styles
            styles_result = self.cdp.execute("CSS.getComputedStyleForNode", {"nodeId": node_id}, timeout=timeout)

            # Convert styles to dict
            styles = {}
            for prop in styles_result.get("computedStyle", []):
                styles[prop["name"]] = prop["value"]

            # Get box model for badge positioning
            try:
                box_result = self.cdp.execute("DOM.getBoxModel", {"nodeId": node_id}, timeout=timeout)
                # Use top-left corner of content box
                content_box = box_result["model"]["content"]
                badge_x = int(content_box[0])  # Top-left x
                badge_y = int(content_box[1])  # Top-left y
            except Exception:
                # Fallback if element has no box model (display: none, etc.)
                badge_x = 0
                badge_y = 0

        except TimeoutError as e:
            logger.warning(f"Timeout extracting node {backend_node_id}: {e}")
            raise RuntimeError("Element selection timed out - page may be busy or unresponsive") from e

        # Generate CSS selector
        css_selector = self._generate_css_selector(node)

        # Generate XPath
        xpath = self._generate_xpath(node)

        # Generate jsPath (for js() command integration)
        js_path = f"document.querySelector('{css_selector}')"

        # Build preview
        tag = node.get("nodeName", "").lower()
        node_attrs = node.get("attributes", [])
        attrs_dict = {}
        for i in range(0, len(node_attrs), 2):
            if i + 1 < len(node_attrs):
                attrs_dict[node_attrs[i]] = node_attrs[i + 1]

        preview = {
            "tag": tag,
            "id": attrs_dict.get("id", ""),
            "classes": attrs_dict.get("class", "").split() if attrs_dict.get("class") else [],
            "text": self._get_node_text(outer_html)[:100],  # First 100 chars
        }

        # Build complete data structure (compatible with existing schema)
        return {
            "outerHTML": outer_html,
            "selector": css_selector,
            "jsPath": js_path,
            "styles": styles,
            "xpath": xpath,
            "fullXpath": xpath,  # CDP doesn't distinguish, use same
            "preview": preview,
            "badge": {"x": badge_x, "y": badge_y},
            "nodeId": node_id,
            "backendNodeId": backend_node_id,
        }

    def _generate_css_selector(self, node: dict) -> str:
        """Generate unique CSS selector for node.

        Uses a combination of strategies to ensure uniqueness:
        1. ID if available (most unique)
        2. Tag + classes + nth-child for specificity
        3. Falls back to full path if needed

        Args:
            node: CDP node description

        Returns:
            CSS selector string
        """
        # Parse attributes
        attrs_dict = self._parse_node_attributes(node)

        # Strategy 1: ID selector (unique by definition)
        if "id" in attrs_dict and attrs_dict["id"]:
            return f"#{attrs_dict['id']}"

        # Strategy 2: Build selector with tag + classes + nth-child
        tag = node.get("nodeName", "").lower()
        selector = tag

        # Add first 2 classes for specificity without being too brittle
        if "class" in attrs_dict and attrs_dict["class"]:
            classes = attrs_dict["class"].split()[:2]
            if classes:
                selector += "." + ".".join(classes)

        # Add nth-child for uniqueness within parent
        # This is key to distinguishing elements with same tag/class
        parent_id = node.get("parentId")
        if parent_id and self.cdp:
            try:
                # Get parent node to count children
                parent_result = self.cdp.execute("DOM.describeNode", {"nodeId": parent_id}, timeout=5.0)

                if "node" in parent_result:
                    parent_node = parent_result["node"]
                    child_node_ids = parent_node.get("childNodeIds", [])

                    # Find our position among siblings
                    node_id = node.get("nodeId")
                    if node_id in child_node_ids:
                        nth = child_node_ids.index(node_id) + 1
                        selector += f":nth-child({nth})"

            except Exception as e:
                logger.debug(f"Could not add nth-child to selector: {e}")

        return selector

    def _parse_node_attributes(self, node: dict) -> dict:
        """Parse CDP node attributes array into dictionary.

        Args:
            node: CDP node with attributes array [name1, value1, name2, value2, ...]

        Returns:
            Dictionary of {name: value}
        """
        attrs = node.get("attributes", [])
        attrs_dict = {}
        for i in range(0, len(attrs), 2):
            if i + 1 < len(attrs):
                attrs_dict[attrs[i]] = attrs[i + 1]
        return attrs_dict

    def _generate_xpath(self, node: dict) -> str:
        """Generate XPath for node.

        Args:
            node: CDP node description

        Returns:
            XPath string
        """
        tag = node.get("nodeName", "").lower()
        attrs_dict = self._parse_node_attributes(node)

        # Prefer ID (unique)
        if "id" in attrs_dict and attrs_dict["id"]:
            return f"//{tag}[@id='{attrs_dict['id']}']"

        # Use class attribute if available
        if "class" in attrs_dict and attrs_dict["class"]:
            # XPath class matching (contains all classes)
            classes = attrs_dict["class"].split()
            if classes:
                return f"//{tag}[@class='{attrs_dict['class']}']"

        # Fallback to tag only
        return f"//{tag}"

    def _get_node_text(self, html: str) -> str:
        """Extract text content from HTML (simple implementation).

        Args:
            html: Outer HTML string

        Returns:
            Extracted text content
        """
        # Simple regex to strip tags
        text = re.sub(r"<[^>]+>", "", html)
        return text.strip()

    def get_state(self) -> dict[str, Any]:
        """Get current DOM service state (thread-safe).

        Returns:
            State dictionary with inspect_active, selections, and pending count
        """
        # Thread-safe read: protect against concurrent writes from WebSocket thread
        with self._state_lock:
            selections = {}
            prompt = ""

            if self.state is not None and self.state.browser_data:
                # Deep copy to prevent mutations during SSE broadcast
                selections = dict(self.state.browser_data.get("selections", {}))
                prompt = self.state.browser_data.get("prompt", "")

        return {
            "inspect_active": self._inspection_active,
            "selections": selections,
            "prompt": prompt,
            "pending_count": self._pending_selections,  # For progress indicator
        }

    def clear_selections(self) -> None:
        """Clear all selections (thread-safe)."""
        with self._state_lock:
            if self.state is not None and self.state.browser_data:
                self.state.browser_data["selections"] = {}
            self._next_id = 1
        logger.info("Selections cleared")
        self._trigger_broadcast()

    def cleanup(self) -> None:
        """Cleanup resources (executor, callbacks).

        Call this before disconnect or app exit.
        Safe to call multiple times.
        """
        # Shutdown executor - wait=False to avoid blocking on stuck tasks
        # cancel_futures=True prevents hanging on incomplete selections
        if hasattr(self, "_executor"):
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
                logger.info("ThreadPoolExecutor shut down")
            except Exception as e:
                logger.debug(f"Executor shutdown error (non-fatal): {e}")

        # Clear inspection state (only if connected)
        if self._inspection_active and self.cdp and self.cdp.is_connected:
            try:
                self.stop_inspect()
            except Exception as e:
                logger.debug(f"Failed to stop inspect on cleanup: {e}")

        # Force clear inspection flag even if CDP call failed
        self._inspection_active = False


__all__ = ["DOMService"]
