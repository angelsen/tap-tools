"""Shell script builder with descriptive names and inline math.

PUBLIC API:
  - ShellBuilder: Clean shell script builder for generating gum command sequences
"""

import shlex
from typing import List, Optional


class ShellBuilder:
    """Clean shell script builder with explicit variable names."""

    def __init__(self):
        """Initialize builder."""
        self.commands: List[str] = []
        self.declarations: List[str] = []  # Variable declarations with comments
        self.result_counter: int = 0
        self.result_var: Optional[str] = None

    def add_variable(self, name: str, value: str, comment: Optional[str] = None) -> str:
        """Add a variable declaration with optional comment."""
        if comment:
            self.declarations.append(f"# {comment}")
        self.declarations.append(f"{name}={value}")
        return f"${name}"

    def add_command(self, cmd: List[str], capture: bool = False, result_name: Optional[str] = None) -> str:
        """Add command to script. Returns variable name if capturing."""
        cmd_str = " ".join(arg if arg.startswith("$") else shlex.quote(arg) for arg in cmd)

        if capture:
            var_name = result_name or f"RESULT_{self.result_counter}"
            self.result_counter += 1
            self.commands.append(f"{var_name}=$({cmd_str})")
            return var_name
        else:
            self.commands.append(cmd_str)
            return ""

    def add_pipe(self, input_var: str, cmd: List[str], capture: bool = False, result_name: Optional[str] = None) -> str:
        """Pipe a variable's content to a command."""
        cmd_str = " ".join(arg if arg.startswith("$") else shlex.quote(arg) for arg in cmd)

        pipe_cmd = f'echo "${{{input_var}}}" | {cmd_str}'

        if capture:
            var_name = result_name or f"RESULT_{self.result_counter}"
            self.result_counter += 1
            self.commands.append(f"{var_name}=$({pipe_cmd})")
            return var_name
        else:
            self.commands.append(pipe_cmd)
            return ""

    def add_literal(self, text: str, var_name: Optional[str] = None) -> str:
        """Store literal text in a variable."""
        name = var_name or f"TEXT_{self.result_counter}"
        self.result_counter += 1
        escaped_text = text.replace("'", "'\\''")
        self.commands.append(f"{name}='{escaped_text}'")
        return name

    def add_join(self, items: List[str], vertical: bool = True, result_name: Optional[str] = None) -> str:
        """Join multiple items with gum join."""
        orientation = "--vertical" if vertical else "--horizontal"
        var_refs = [f'"${{{item}}}"' for item in items]

        cmd_str = f"gum join {orientation} {' '.join(var_refs)}"

        var_name = result_name or f"JOINED_{self.result_counter}"
        self.result_counter += 1
        self.commands.append(f"{var_name}=$({cmd_str})")
        return var_name

    def add_style(
        self,
        content_var: str,
        width: Optional[str] = None,
        height: Optional[str] = None,
        border: str = "none",
        align: Optional[str] = None,
        padding: Optional[str] = None,
        margin: Optional[str] = None,
        result_name: Optional[str] = None,
    ) -> str:
        """Add gum style command with explicit dimensions.

        Rule: Only pass --border flag for real borders (not "none" or "hidden").
        Margin is passed directly to gum which handles the spacing.
        """
        cmd = ["gum", "style", "--no-strip-ansi"]  # Preserve ANSI colors

        if width:
            cmd.extend(["--width", width])
        if height:
            cmd.extend(["--height", height])

        # Only pass border flag for real borders
        if border and border not in ["none", "hidden"]:
            cmd.extend(["--border", border])

        if align:
            cmd.extend(["--align", align])
        if padding:
            cmd.extend(["--padding", padding])
        if margin:
            cmd.extend(["--margin", margin])

        return self.add_pipe(content_var, cmd, capture=True, result_name=result_name)

    def add_interactive(self, element, cmd: List[str]) -> str:
        """Add interactive element with proper TTY handling."""
        import shlex

        needs_tty = getattr(element, "_needs_tty", False)
        capture_output = getattr(element, "_capture_output", True)
        use_exit_code = getattr(element, "_use_exit_code", False)

        has_stdin = hasattr(element, "_parse_hints") and "stdin_data" in element._parse_hints
        stdin_data = element._parse_hints["stdin_data"] if has_stdin else None

        # Exit code based (Confirm)
        if use_exit_code:
            result_var = f"CONFIRM_RESULT_{self.result_counter}"
            self.result_counter += 1
            cmd_str = " ".join(shlex.quote(str(arg)) for arg in cmd)

            if has_stdin and stdin_data is not None:
                data_var = self.add_literal(stdin_data)
                self.commands.extend(
                    [
                        f'if echo "${{{data_var}}}" | {cmd_str}; then',
                        f"    {result_var}='true'",
                        "else",
                        f"    {result_var}='false'",
                        "fi",
                    ]
                )
            else:
                self.commands.extend(
                    [f"if {cmd_str}; then", f"    {result_var}='true'", "else", f"    {result_var}='false'", "fi"]
                )

            self.result_var = result_var
            return result_var

        # TTY interactive (Input, Choose, etc.)
        if needs_tty:
            if not capture_output:
                # Pager - no capture
                if has_stdin and stdin_data is not None:
                    data_var = self.add_literal(stdin_data)
                    cmd_str = " ".join(shlex.quote(str(arg)) for arg in cmd)
                    self.commands.append(f'echo "${{{data_var}}}" | {cmd_str}')
                else:
                    cmd_str = " ".join(shlex.quote(str(arg)) for arg in cmd)
                    self.commands.append(cmd_str)
                return ""
            else:
                # Interactive with capture
                result_var = f"INPUT_RESULT_{self.result_counter}"
                self.result_counter += 1
                cmd_str = " ".join(shlex.quote(str(arg)) for arg in cmd)
                temp_file = f"/tmp/tmux_popup_{result_var}.txt"

                if has_stdin and stdin_data is not None:
                    data_var = self.add_literal(stdin_data)
                    self.commands.append(f'echo "${{{data_var}}}" | {cmd_str} > {shlex.quote(temp_file)}')
                else:
                    self.commands.append(f"{cmd_str} > {shlex.quote(temp_file)}")

                self.commands.append(f"{result_var}=$(cat {shlex.quote(temp_file)})")
                self.commands.append(f"rm -f {shlex.quote(temp_file)}")
                self.result_var = result_var
                return result_var

        # Pipe-safe commands
        if has_stdin and stdin_data is not None:
            data_var = self.add_literal(stdin_data)
            if capture_output:
                return self.add_pipe(data_var, cmd, capture=True)
            else:
                self.add_pipe(data_var, cmd, capture=False)
                return ""
        else:
            if capture_output:
                result_var = self.add_command(cmd, capture=True)
                self.result_var = result_var
                return result_var
            else:
                cmd_str = " ".join(shlex.quote(str(arg)) for arg in cmd)
                self.commands.append(cmd_str)
                return ""

    def build(self, interactive: bool = False, result_file: Optional[str] = None) -> str:
        """Build final shell script."""
        lines = [
            "#!/bin/bash",
            "set -euo pipefail",
            "",
            "# Popup dimensions (inside tmux popup, these are the popup's dimensions)",
            "POPUP_WIDTH=$(tput cols)",
            "POPUP_HEIGHT=$(tput lines)",
            "",
        ]

        # Add variable declarations
        if self.declarations:
            lines.append("# Layout calculations")
            lines.extend(self.declarations)
            lines.append("")

        # Add commands
        if self.commands:
            lines.append("# Execute")
            lines.extend(self.commands)

        # Handle output
        if interactive:
            lines.append("")
            lines.append('read -s -n 1 -p "Press any key to close..."')
        elif result_file and self.result_var:
            lines.append("")
            lines.append(f'echo "${{{self.result_var}}}" > {shlex.quote(result_file)}')

        return "\n".join(lines)
