"""Hook management for pattern-triggered actions.

PUBLIC API:
  - Hook: Single hook configuration
  - HookManager: Check and track hook firing
"""

import time
from dataclasses import dataclass, field

from .patterns import dsl_matches, split_output

__all__ = ["Hook", "HookManager"]


@dataclass
class Hook:
    """A single hook configuration."""

    pattern: str
    action: str
    keys: list[str] = field(default_factory=list)
    debounce: float = 2.0
    _last_fired: float = 0.0

    def matches_lines(self, output_lines: list[str]) -> bool:
        return dsl_matches(self.pattern, output_lines)

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
        hooks = self.hooks.get(process)
        if not hooks:
            return []
        output_lines = split_output(output)  # split once for all hooks
        return [h for h in hooks if h.matches_lines(output_lines) and h.can_fire()]


def _parse_debounce(value: str) -> float:
    if not value or value == "0":
        return 0.0
    value = value.strip().lower()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000.0
    elif value.endswith("s"):
        return float(value[:-1])
    return float(value)
