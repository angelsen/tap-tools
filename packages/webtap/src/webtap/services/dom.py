"""DOM inspection service using Chrome DevTools Protocol.

PUBLIC API:
  - DOMService: Element inspection and selection via CDP Overlay domain
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)


class DOMService:
    """Manages element inspection and selection via CDP Overlay domain.

    Uses CDP's native inspect mode (Overlay.setInspectMode) which provides:
    - Native Chrome highlight on hover (no custom overlay needed)
    - Click events via Overlay.inspectNodeRequested
    - Accurate element data via DOM.describeNode, CSS.getComputedStyleForNode

    Selections are stored in service.state.browser_data (not DuckDB) as they are
    ephemeral session data cleared after prompt submission.

    Attributes:
        service: WebTapService reference for multi-target operations and state access
        _inspect_target: Currently inspected target ID
        _next_id: Counter for assigning selection IDs
    """

    def __init__(self):
        """Initialize DOM service."""
        self.service: "Any" = None  # WebTapService reference
        self._inspect_target: str | None = None  # Currently inspected target
        self._next_id = 1
        self._state_lock = threading.RLock()  # Protect state mutations (RLock for re-entry)
        self._pending_selections = 0  # Track in-flight selection processing
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dom-worker")
        self._shutdown = False  # Prevent executor submissions after cleanup
        self._generation = 0  # Incremented on clear to invalidate stale pending selections

    def set_service(self, service: "Any") -> None:
        """Set service reference.

        Args:
            service: WebTapService instance
        """
        self.service = service

    def reset(self) -> None:
        """Reset service state for new connection.

        Call when reconnecting to a new page after previous disconnect.
        Creates fresh executor and clears shutdown flag.
        """
        self._shutdown = False
        self._inspect_target = None
        self._pending_selections = 0
        self._generation += 1  # Invalidate stale pending work

        # Create fresh executor (old one was shutdown)
        if hasattr(self, "_executor"):
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dom-worker")
        logger.info("DOMService reset for new connection")

    def start_inspect(self, target: str) -> dict[str, Any]:
        """Enable CDP element inspection mode on a specific target.

        Args:
            target: Target ID to inspect

        Enables Overlay.setInspectMode with searchForNode mode, which:
        - Shows native Chrome highlight on hover
        - Fires Overlay.inspectNodeRequested on click

        Returns:
            Success status dictionary.
        """
        if not self.service:
            return {"error": "No service"}

        conn = self.service.connections.get(target)
        if not conn or not conn.cdp.ws_app:
            return {"error": f"Target {target} not connected"}

        # Disable on previous target if different
        if self._inspect_target and self._inspect_target != target:
            self._disable_inspect_on_target(self._inspect_target)

        # If already inspecting THIS target, unregister callbacks first to prevent duplicates
        if self._inspect_target == target:
            cdp = conn.cdp
            cdp.unregister_event_callback("Overlay.inspectNodeRequested", self.handle_inspect_node_requested)
            cdp.unregister_event_callback("Page.frameNavigated", self.handle_frame_navigated)

        cdp = conn.cdp

        try:
            # Enable DOM domain first (Overlay depends on it)
            cdp.execute("DOM.enable")

            # Request document to establish DOM tree context
            # REQUIRED: BackendNodeIds only work after getDocument() is called
            cdp.execute("DOM.getDocument", {"depth": -1})

            # Enable CSS domain (needed for computed styles)
            cdp.execute("CSS.enable")

            # Enable Overlay domain
            cdp.execute("Overlay.enable")

            # Set inspect mode with native Chrome highlighting
            cdp.execute(
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

            # Register event callbacks for this target
            cdp.register_event_callback("Overlay.inspectNodeRequested", self.handle_inspect_node_requested)
            cdp.register_event_callback("Page.frameNavigated", self.handle_frame_navigated)

            self._inspect_target = target
            logger.info(f"Element inspection mode enabled on {target}")

            self._trigger_broadcast()
            return {"success": True, "inspect_active": True, "target": target}

        except Exception as e:
            logger.error(f"Failed to enable inspection mode: {e}")
            return {"error": str(e)}

    def stop_inspect(self) -> dict[str, Any]:
        """Disable CDP element inspection mode on current target.

        Returns:
            Success status dictionary.
        """
        if not self._inspect_target:
            return {"success": True, "inspect_active": False}

        result = self._disable_inspect_on_target(self._inspect_target)
        self._inspect_target = None
        self._trigger_broadcast()
        return result

    def _disable_inspect_on_target(self, target: str) -> dict[str, Any]:
        """Disable inspect mode on a specific target.

        Args:
            target: Target ID to disable inspection on

        Returns:
            Status dictionary
        """
        if not self.service:
            return {"error": "No service"}

        conn = self.service.connections.get(target)
        if not conn or not conn.cdp.ws_app:
            return {"success": True, "inspect_active": False}  # Already disconnected

        try:
            # Disable inspect mode
            # NOTE: highlightConfig required even for mode=none, otherwise CDP throws:
            # "Internal error: highlight configuration parameter is missing"
            conn.cdp.execute("Overlay.setInspectMode", {"mode": "none", "highlightConfig": {}})

            logger.info(f"Element inspection mode disabled on {target}")
            return {"success": True, "inspect_active": False}

        except Exception as e:
            logger.error(f"Failed to disable inspection mode on {target}: {e}")
            return {"error": str(e)}

    def _get_inspect_cdp(self):
        """Get CDPSession for current inspect target."""
        if not self.service or not self._inspect_target:
            return None
        conn = self.service.connections.get(self._inspect_target)
        return conn.cdp if conn else None

    def handle_inspect_node_requested(self, event: dict) -> None:
        """Handle Overlay.inspectNodeRequested event (user clicked element).

        CRITICAL: Called from WebSocket thread - MUST NOT make blocking CDP calls!
        Offload to background thread to avoid deadlock.

        Args:
            event: CDP event with method and params
        """
        cdp = self._get_inspect_cdp()
        if not cdp or not self.service.state:
            logger.error("DOMService not properly initialized (missing cdp or state)")
            return

        params = event.get("params", {})
        backend_node_id = params.get("backendNodeId")
        if not backend_node_id:
            logger.warning("inspectNodeRequested event missing backendNodeId")
            return

        # Check if shutdown before submitting to executor
        if self._shutdown:
            logger.debug("Ignoring inspect event - service shutting down")
            return

        # Increment pending counter and capture generation (thread-safe)
        with self._state_lock:
            self._pending_selections += 1
            current_generation = self._generation
        self._trigger_broadcast()

        # Submit to background thread - returns immediately, no blocking
        # Pass generation to detect stale selections after clear_selections()
        self._executor.submit(self._process_node_selection, backend_node_id, current_generation)

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

    def _process_node_selection(self, backend_node_id: int, expected_generation: int) -> None:
        """Process node selection in background thread.

        Safe to make blocking CDP calls here - we're not in WebSocket thread.

        Args:
            backend_node_id: CDP backend node ID from inspectNodeRequested event
            expected_generation: Generation counter when selection was initiated.
                If current generation differs, selection is dropped (page disconnected).
        """
        try:
            # Make blocking CDP calls (OK in background thread)
            data = self._extract_node_data(backend_node_id)

            # Thread-safe state update
            with self._state_lock:
                # Check generation to drop stale selections from previous connections
                if self._generation != expected_generation:
                    logger.debug(f"Dropping stale selection (gen {expected_generation} != {self._generation})")
                    return

                if not self.service.state:
                    logger.error("DOMService state not initialized")
                    return

                selection_id = str(self._next_id)
                self._next_id += 1

                self.service.set_browser_selection(selection_id, data)

            logger.info(f"Element selected: {selection_id} - {data.get('preview', {}).get('tag', 'unknown')}")

        except Exception as e:
            logger.error(f"Failed to process node selection: {e}")
            # Set error state for UI display
            if self.service.state:
                import time

                error_msg = str(e)
                # Provide user-friendly message for common errors
                if "timed out" in error_msg.lower() or isinstance(e, TimeoutError):
                    error_msg = "Element selection timed out - page may be unresponsive"
                # Use per-target error format
                if not isinstance(self.service.state.error_state, dict):
                    self.service.state.error_state = {}
                self.service.state.error_state["global"] = {"message": error_msg, "timestamp": time.time()}
        finally:
            # Decrement pending counter (thread-safe)
            with self._state_lock:
                self._pending_selections -= 1
            self._trigger_broadcast()

    def _trigger_broadcast(self) -> None:
        """Trigger SSE broadcast via service (ensures snapshot update)."""
        if self.service:
            try:
                self.service._trigger_broadcast()
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
        cdp = self._get_inspect_cdp()
        if not cdp:
            raise RuntimeError("CDP session not initialized")

        # Use 15s timeout for interactive operations (balanced between responsiveness and heavy pages)
        # Still shorter than default 30s to provide faster failure feedback
        timeout = 15.0

        try:
            # Describe node directly with backendNodeId (no need for resolveNode first!)
            describe_result = cdp.execute("DOM.describeNode", {"backendNodeId": backend_node_id}, timeout=timeout)

            if "node" not in describe_result:
                raise RuntimeError(f"Failed to describe node {backend_node_id}")

            node = describe_result["node"]
            node_id = node["nodeId"]

            # Get outer HTML
            html_result = cdp.execute("DOM.getOuterHTML", {"nodeId": node_id}, timeout=timeout)
            outer_html = html_result.get("outerHTML", "")

            # Get computed styles
            styles_result = cdp.execute("CSS.getComputedStyleForNode", {"nodeId": node_id}, timeout=timeout)

            # Convert styles to dict
            styles = {}
            for prop in styles_result.get("computedStyle", []):
                styles[prop["name"]] = prop["value"]

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
        cdp = self._get_inspect_cdp()
        if parent_id and cdp:
            try:
                # Get parent node to count children
                parent_result = cdp.execute("DOM.describeNode", {"nodeId": parent_id}, timeout=5.0)

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
            State dictionary with inspect_active, inspecting target, selections, and pending count
        """
        # Thread-safe read: protect against concurrent writes from WebSocket thread
        with self._state_lock:
            if self.service.state is not None:
                selections, prompt = self.service.get_browser_data()
            else:
                selections, prompt = {}, ""

        return {
            "inspect_active": self._inspect_target is not None,
            "inspecting": self._inspect_target,  # Which target is being inspected
            "selections": selections,
            "prompt": prompt,
            "pending_count": self._pending_selections,  # For progress indicator
        }

    def clear_selections(self) -> None:
        """Clear all selections (thread-safe).

        Increments generation counter to invalidate any pending selection workers,
        preventing stale selections from previous connections appearing in new ones.
        """
        with self._state_lock:
            # Increment generation FIRST to invalidate all pending workers
            self._generation += 1
            if self.service.state is not None:
                self.service.clear_browser_selections()
            self._next_id = 1
        logger.info(f"Selections cleared (generation {self._generation})")

    def cleanup(self) -> None:
        """Cleanup resources (executor, callbacks).

        Call this before disconnect or app exit.
        Safe to call multiple times.
        """
        # Set shutdown flag first to prevent new submissions
        self._shutdown = True

        # Shutdown executor - wait=False to avoid blocking on stuck tasks
        # cancel_futures=True prevents hanging on incomplete selections
        if hasattr(self, "_executor"):
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
                logger.info("ThreadPoolExecutor shut down")
            except Exception as e:
                logger.debug(f"Executor shutdown error (non-fatal): {e}")

        # Clear inspection state (only if inspecting)
        if self._inspect_target:
            try:
                self.stop_inspect()
            except Exception as e:
                logger.debug(f"Failed to stop inspect on cleanup: {e}")

        # Force clear inspection target even if CDP call failed
        self._inspect_target = None


__all__ = ["DOMService"]
