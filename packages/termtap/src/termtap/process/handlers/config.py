"""Handler configuration from markdown files.

PUBLIC API:
  - ensure_handlers_file: Ensure handlers.md exists on startup
"""

import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass


DEFAULT_TEMPLATE = '''```
HANDLER CONFIGURATION

Available Handlers: SSH, PYTHON, CLAUDE
Actions: auto, ask, never
Timeout: 2s, 5s, 10s, 30s

Syntax:
# HANDLER_NAME
## Group Name (action, timeout)
- pattern
- ~disabled~
- pattern # comment

Example:
# SSH
## Safe Commands (auto, 2s)
- ls *
- pwd
- ~clear~  # disabled
```
'''


@dataclass
class _HandlerRule:
    """Single handler rule with pattern, action, and timeout."""
    pattern: str
    action: str  # "auto", "ask", "never"
    timeout: float
    
    def matches(self, command: str) -> bool:
        """Check if command matches this pattern."""
        # Convert shell wildcard to regex
        pattern = re.escape(self.pattern)
        pattern = pattern.replace(r'\*', '.*')
        pattern = '^' + pattern
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
        lines = content.split('\n')
        
        current_handler = None
        current_action = "ask"
        current_timeout = 10.0
        in_code_block = False
        
        for line in lines:
            # Skip code blocks
            if line.strip() == '```':
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            
            # Handler heading (# SSH)
            if line.startswith('# ') and not line.startswith('##'):
                handler_name = line[2:].strip().upper()
                if handler_name and not handler_name.startswith('EXAMPLE'):
                    current_handler = handler_name
                    if handler_name not in patterns:
                        patterns[handler_name] = []
            
            # Group heading (## Safe Commands (auto, 2s))
            elif line.startswith('## '):
                group_match = re.match(r'## .* \((\w+)(?:, (\d+)s?)?\)', line)
                if group_match:
                    current_action = group_match.group(1)
                    if group_match.group(2):
                        timeout_str = group_match.group(2).rstrip('s')
                        try:
                            current_timeout = float(timeout_str)
                        except ValueError:
                            current_timeout = 10.0
            
            # Pattern line (- ls *)
            elif line.strip().startswith('- ') and current_handler:
                pattern_line = line.strip()[2:].strip()
                
                # Skip disabled patterns (~pattern~)
                if pattern_line.startswith('~') and '~' in pattern_line[1:]:
                    continue
                
                # Remove inline comments
                if '#' in pattern_line:
                    pattern_line = pattern_line.split('#')[0].strip()
                
                if pattern_line:
                    rule = _HandlerRule(
                        pattern=pattern_line,
                        action=current_action,
                        timeout=current_timeout
                    )
                    patterns[current_handler].append(rule)
        
        return patterns
    
    def get_action(self, handler_name: str, command: str) -> Tuple[Optional[str], float]:
        """Get action and timeout for a command.
        
        Args:
            handler_name: Name of handler (e.g., "SSH")
            command: Command to check
            
        Returns:
            Tuple of (action, timeout) or (None, 10.0) if no match
        """
        patterns = self._load_patterns()
        
        handler_name = handler_name.upper()
        if handler_name not in patterns:
            return None, 10.0
        
        # Check patterns in order (first match wins)
        for rule in patterns[handler_name]:
            if rule.matches(command):
                return rule.action, rule.timeout
        
        return None, 10.0


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