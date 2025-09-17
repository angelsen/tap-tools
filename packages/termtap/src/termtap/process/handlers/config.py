"""Handler configuration from markdown files.

PUBLIC API:
  - ensure_handlers_file: Ensure handlers.md exists on startup
"""

import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass


DEFAULT_TEMPLATE = """```
HANDLER CONFIGURATION

Available Handlers: CONFIRMATION, PYTHON, CLAUDE
Actions: auto, ask, never, auto-ask, ask-ask
Timeout: 2s, 5s, 10s, 30s
Line Endings: lf (Unix), crlf (Windows), cr (Mac Classic)

Note: CONFIRMATION handler manages SSH connections and all processes
on systems without /proc (macOS, BSD).

Syntax:
# HANDLER_NAME
## Group Name (action, timeout)        # Unix/Linux (default)
## Group Name (action, timeout, crlf)  # Windows servers
- pattern
- ~disabled~
- pattern # comment

Actions:
- auto: Send automatically, wait for timeout
- ask: Ask before sending, wait for timeout
- never: Block command
- auto-ask: Send automatically, ask when done
- ask-ask: Ask before sending, ask when done

Example:
# CONFIRMATION
## Safe Commands (auto, 2s)
- ls
- pwd

## Windows Commands (auto, 2s, crlf)
- dir
- ipconfig

## Interactive Commands (auto-ask, 5s)  # Ask when done
- vim *
- nano *

## File Operations (ask, 5s)
- rm *
- cp *

## Dangerous (never)
- sudo *
- rm -rf *
```
"""


@dataclass
class _HandlerRule:
    """Single handler rule with pattern, action, timeout, and line ending."""

    pattern: str
    action: str  # "auto", "ask", "never", "auto-ask", "ask-ask"
    timeout: float
    line_ending: str = "lf"  # "lf", "crlf", "cr", ""

    def matches(self, command: str) -> bool:
        """Check if command matches this pattern."""
        # Convert shell wildcard to regex
        pattern = re.escape(self.pattern)
        pattern = pattern.replace(r"\*", ".*")
        pattern = "^" + pattern
        try:
            return bool(re.match(pattern, command))
        except re.error:
            return False


class _HandlerConfig:
    """Configuration manager for handler patterns from markdown files."""

    def _load_patterns(self) -> dict:
        """Load and parse handlers.md file."""
        handlers_path = Path.cwd() / "handlers.md"
        if not handlers_path.exists():
            return {}

        try:
            content = handlers_path.read_text()
            return self._parse_content(content)
        except Exception:
            # Silently ignore errors
            return {}

    def _parse_content(self, content: str) -> dict:
        """Parse markdown content into handler rules."""
        patterns = {}
        lines = content.split("\n")

        current_handler = None
        current_action = "ask"
        current_timeout = 10.0
        current_line_ending = "lf"
        in_code_block = False

        for line in lines:
            # Skip code blocks
            if line.strip() == "```":
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            # Handler heading (# SSH)
            if line.startswith("# ") and not line.startswith("##"):
                handler_name = line[2:].strip().upper()
                if handler_name and not handler_name.startswith("EXAMPLE"):
                    current_handler = handler_name
                    if handler_name not in patterns:
                        patterns[handler_name] = []

            # Group heading (## Safe Commands (auto, 2s) or ## Windows Commands (auto, 2s, crlf))
            elif line.startswith("## "):
                # Match pattern with optional line ending (allow hyphenated actions)
                group_match = re.match(r"## .* \(([\w-]+)(?:, (\d+)s?)?(?:, (\w+))?\)", line)
                if group_match:
                    current_action = group_match.group(1)
                    current_line_ending = "lf"  # default

                    if group_match.group(2):
                        timeout_str = group_match.group(2).rstrip("s")
                        try:
                            current_timeout = float(timeout_str)
                        except ValueError:
                            current_timeout = 10.0

                    if group_match.group(3):
                        # Line ending specified (lf, crlf, cr)
                        ending = group_match.group(3).lower()
                        if ending in ["lf", "crlf", "cr", "none"]:
                            current_line_ending = ending if ending != "none" else ""

            # Pattern line (- ls *)
            elif line.strip().startswith("- ") and current_handler:
                pattern_line = line.strip()[2:].strip()

                # Skip disabled patterns (~pattern~)
                if pattern_line.startswith("~") and "~" in pattern_line[1:]:
                    continue

                # Remove inline comments
                if "#" in pattern_line:
                    pattern_line = pattern_line.split("#")[0].strip()

                if pattern_line:
                    rule = _HandlerRule(
                        pattern=pattern_line,
                        action=current_action,
                        timeout=current_timeout,
                        line_ending=current_line_ending,
                    )
                    patterns[current_handler].append(rule)

        return patterns

    def get_action(self, handler_name: str, command: str) -> Tuple[Optional[str], float, str]:
        """Get action, timeout, and line ending for a command.

        Args:
            handler_name: Name of handler (e.g., "SSH")
            command: Command to check

        Returns:
            Tuple of (action, timeout, line_ending) or (None, 10.0, "lf") if no match
        """
        patterns = self._load_patterns()

        handler_name = handler_name.upper()
        if handler_name not in patterns:
            return None, 10.0, "lf"

        # Check patterns in order (first match wins)
        for rule in patterns[handler_name]:
            if rule.matches(command):
                return rule.action, rule.timeout, rule.line_ending

        return None, 10.0, "lf"


_config_instance: Optional[_HandlerConfig] = None


def _get_handler_config() -> _HandlerConfig:
    """Get or create the global handler configuration singleton."""
    global _config_instance
    if _config_instance is None:
        _config_instance = _HandlerConfig()
    return _config_instance


def ensure_handlers_file() -> None:
    """Ensure handlers.md exists in current directory. Called at startup."""
    handlers_path = Path.cwd() / "handlers.md"
    if not handlers_path.exists():
        handlers_path.write_text(DEFAULT_TEMPLATE)
