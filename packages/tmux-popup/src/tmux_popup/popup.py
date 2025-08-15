"""Main container for tmux-popup v3.

PUBLIC API:
  - Popup: Main container that renders everything in a single tmux popup
"""

import subprocess
import tempfile
import os
from typing import Optional, Any
from dataclasses import dataclass

from .core.base import Element, Interactive
from .core.builder import ShellBuilder
from .canvas import Canvas


@dataclass
class Popup:
    """Main container that renders everything in a single tmux popup.

    Can contain:
    - Canvas only (displays with blocking read)
    - Input only (returns value)
    - Canvas + Input (display then input, returns value)
    """

    # Popup dimensions
    width: Optional[str] = None  # e.g. "80%" or "100"
    height: Optional[str] = None  # e.g. "60%" or "30"
    border: bool = True  # Whether tmux popup has border
    debug: bool = False  # Show generated script for debugging

    # Content
    _canvas: Optional[Canvas] = None
    _input: Optional[Element] = None

    def add(self, *elements: Element) -> "Popup":
        """Add elements to popup.

        Rules:
        - Maximum 1 Canvas
        - Maximum 1 Input element
        - Canvas must come before Input
        """
        for element in elements:
            if isinstance(element, Canvas):
                if self._canvas is not None:
                    raise ValueError("Popup can only have one Canvas")
                self._canvas = element
            elif hasattr(element, "render"):
                # It's an interactive element
                if self._input is not None:
                    raise ValueError("Popup can only have one input element")
                self._input = element
            else:
                raise ValueError(f"Popup can only contain Canvas or Interactive elements, not {type(element).__name__}")

        return self

    def show(self) -> Optional[Any]:
        """Display the popup and return any input result.

        Returns:
            None if Canvas only, input value if Input present
        """
        # Build the shell script
        builder = ShellBuilder()

        # Track which commands are used for debug help
        commands_used = set()

        # Render canvas if present
        if self._canvas:
            canvas_result = self._canvas.render(builder)
            if canvas_result:
                # Output the canvas
                builder.commands.append(f'echo "${{{canvas_result}}}"')

        # Render input if present
        if self._input:
            self._input.render(builder)
            # Track the command for help output
            if isinstance(self._input, Interactive):
                commands_used.add(self._input._gum_command)

        # Determine mode
        needs_blocking = bool(self._canvas and not self._input)

        # Create temp file for result if we have input
        result_file = None
        if self._input:
            with tempfile.NamedTemporaryFile(mode="w", suffix="_result.txt", delete=False) as f:
                result_file = f.name

        # Build script with result file if needed
        script = builder.build(interactive=needs_blocking, result_file=result_file)

        # Debug output
        if self.debug:
            print(script)

        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name

        os.chmod(script_path, 0o755)

        # Build tmux command
        tmux_cmd = ["tmux", "display-popup"]

        if self.width:
            tmux_cmd.extend(["-w", self.width])
        if self.height:
            tmux_cmd.extend(["-h", self.height])
        if not self.border:
            tmux_cmd.append("-B")

        tmux_cmd.extend(["-E", script_path])

        try:
            # Run tmux popup
            result = subprocess.run(tmux_cmd, capture_output=True, text=True)

            # Check for errors
            if result.returncode != 0 and result.stderr:
                print(f"Error running popup: {result.stderr}")

            # Read result from temp file if we have input
            if result_file and os.path.exists(result_file):
                with open(result_file, "r") as f:
                    raw_result = f.read()

                # Use the interactive element's parser if available
                if self._input and isinstance(self._input, Interactive):
                    # Get exit code from subprocess result
                    return self._input.parse_result(raw_result, result.returncode)

                # Fallback to raw string
                return raw_result.strip() if raw_result else None

            return None

        finally:
            # Clean up temp files
            if os.path.exists(script_path):
                os.unlink(script_path)
            if result_file and os.path.exists(result_file):
                os.unlink(result_file)
