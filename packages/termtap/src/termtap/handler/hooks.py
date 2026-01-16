"""Hook management for pattern-triggered actions.

PUBLIC API:
  - Hook: Single hook configuration
  - HookManager: Check and track hook firing
"""

import re
import time
from dataclasses import dataclass, field

from .patterns import compile_dsl

__all__ = ["Hook", "HookManager"]


@dataclass
class Hook:
    """A single hook configuration."""

    pattern: str
    action: str
    keys: list[str] = field(default_factory=list)
    debounce: float = 2.0
    _last_fired: float = 0.0
    _regex: re.Pattern | None = field(default=None, repr=False)

    @property
    def regex(self) -> re.Pattern:
        if self._regex is None:
            self._regex = compile_dsl(self.pattern)
        return self._regex

    def matches(self, output: str) -> bool:
        lines = [line.rstrip() for line in output.rstrip("\n").split("\n")]
        return any(self.regex.search(line) for line in lines)

    def can_fire(self) -> bool:
        if self.debounce <= 0:
            return True
        return (time.time() - self._last_fired) >= self.debounce

    def mark_fired(self) -> None:
        self._last_fired = time.time()


@dataclass
class HookManager:
    """Manages hooks for all processes."""

    hooks: dict[str, list[Hook]] = field(default_factory=dict)

    def load_from_patterns(self, patterns: dict) -> None:
        self.hooks.clear()
        for process, data in patterns.items():
            if "hooks" in data and isinstance(data["hooks"], dict):
                process_hooks = []
                for pattern, config in data["hooks"].items():
                    if isinstance(config, dict):
                        hook = Hook(
                            pattern=pattern,
                            action=config.get("action", "send_keys"),
                            keys=config.get("keys", []),
                            debounce=_parse_debounce(config.get("debounce", "2s")),
                        )
                        process_hooks.append(hook)
                if process_hooks:
                    self.hooks[process] = process_hooks

    def check_hooks(self, process: str, output: str) -> list[Hook]:
        if process not in self.hooks:
            return []
        return [h for h in self.hooks[process] if h.matches(output) and h.can_fire()]


def _parse_debounce(value: str) -> float:
    if not value or value == "0":
        return 0.0
    value = value.strip().lower()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000.0
    elif value.endswith("s"):
        return float(value[:-1])
    return float(value)
