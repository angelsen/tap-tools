"""Pattern storage and matching with DSL support.

PUBLIC API:
  - PatternStore: Load/save/match patterns from YAML
  - Pattern: Single or multi-line pattern with DSL
  - compile_dsl: Compile DSL string to regex
  - DSLError: DSL parsing and compilation errors
"""

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from ..paths import PATTERNS_PATH

if TYPE_CHECKING:
    from .hooks import HookManager

__all__ = ["PatternStore", "Pattern", "PatternPair", "compile_dsl", "DSLError"]


class DSLError(Exception):
    """DSL parsing and compilation errors."""

    pass


def parse_quantifier(dsl: str, pos: int) -> tuple[str, int]:
    """Parse quantifier at position, return (regex_quant, chars_consumed).

    Args:
        dsl: DSL string
        pos: Position to start parsing

    Returns:
        Tuple of (regex quantifier string, number of chars consumed)
    """
    if pos >= len(dsl):
        return ("+", 0)  # Default: one or more

    char = dsl[pos]

    if char == "+":
        return ("+", 1)
    elif char == "*":
        return ("*", 1)
    elif char == "?":
        return ("?", 1)
    elif char.isdigit():
        # Could be exact (4) or range (2-4)
        j = pos
        while j < len(dsl) and (dsl[j].isdigit() or dsl[j] == "-"):
            j += 1
        spec = dsl[pos:j]
        if "-" in spec:
            # Convert DSL range (2-4) to regex range {2,4}
            return (f"{{{spec.replace('-', ',')}}}", j - pos)
        else:
            return (f"{{{spec}}}", j - pos)  # {4}

    return ("+", 0)  # Default


def compile_dsl(dsl: str) -> re.Pattern:
    """Compile DSL string to regex pattern.

    DSL Syntax:
        Types:      #=digit, w=word, .=any, _=space
        Quants:     +=one+, *=zero+, ?=optional, N=exact, N-M=range
        Anchors:    ^=start, $=end
        Literal:    [text]=exact, [N]=gap, [*]=any, [+]=one+

    Args:
        dsl: DSL pattern string

    Returns:
        Compiled regex pattern
    """
    result = []
    i = 0

    while i < len(dsl):
        char = dsl[i]

        # Anchors
        if char == "$" and i == len(dsl) - 1:
            result.append("$")
        elif char == "^" and i == 0:
            result.append("^")

        # Literal brackets
        elif char == "[":
            try:
                end = dsl.index("]", i)
            except ValueError:
                context_start = max(0, i - 5)
                context_end = min(len(dsl), i + 10)
                raise DSLError(
                    f"Invalid DSL pattern at position {i}: unmatched '[' (context: '{dsl[context_start:context_end]}')"
                )
            content = dsl[i + 1 : end]
            if content == "*":
                result.append(".*")
            elif content == "+":
                result.append(".+")
            elif content.isdigit():
                result.append(f".{{{content}}}")  # [31] → .{31}
            else:
                result.append(re.escape(content))  # literal
            i = end

        # Types with quantifiers
        elif char == "#":
            quant, skip = parse_quantifier(dsl, i + 1)
            result.append(f"\\d{quant}")
            i += skip
        elif char == "w":
            quant, skip = parse_quantifier(dsl, i + 1)
            result.append(f"\\w{quant}")
            i += skip
        elif char == "_":
            quant, skip = parse_quantifier(dsl, i + 1)
            result.append(f" {quant}")
            i += skip
        elif char == ".":
            quant, skip = parse_quantifier(dsl, i + 1)
            result.append(f".{quant}")
            i += skip

        # Literal character
        else:
            result.append(re.escape(char))

        i += 1

    return re.compile("".join(result))


@dataclass
class Pattern:
    """Single or multi-line pattern with DSL support."""

    raw: str  # Original DSL string (may have newlines)
    process: str  # Process name
    state: str  # "ready" or "busy"
    _regex: re.Pattern | None = field(default=None, repr=False)

    @property
    def regex(self) -> re.Pattern:
        """Compile DSL to regex (cached)."""
        if self._regex is None:
            self._regex = compile_dsl(self.raw)
        return self._regex

    @property
    def lines(self) -> list[str]:
        """Split into lines for multi-line matching."""
        return self.raw.strip().split("\n")

    @property
    def is_multiline(self) -> bool:
        """Check if pattern spans multiple lines."""
        return "\n" in self.raw

    def matches(self, output: str) -> bool:
        """Check if pattern matches output.

        Single-line: matches if found anywhere.
        Multi-line: matches if consecutive sequence found anywhere.

        Args:
            output: Output text to match against

        Returns:
            True if pattern matches
        """
        # Strip trailing whitespace from each line to normalize between:
        # - tmux capture-pane (strips trailing spaces)
        # - pipe-pane stream (preserves trailing spaces)
        output_lines = [line.rstrip() for line in output.rstrip("\n").split("\n")]
        pattern_lines = self.lines

        if len(output_lines) < len(pattern_lines):
            return False

        # Single-line pattern: search anywhere
        if len(pattern_lines) == 1:
            line_regex = compile_dsl(pattern_lines[0])
            return any(line_regex.search(line) for line in output_lines)

        # Multi-line pattern: find consecutive sequence anywhere
        for start_idx in range(len(output_lines) - len(pattern_lines) + 1):
            match = True
            for i, pattern_line in enumerate(pattern_lines):
                line_regex = compile_dsl(pattern_line)
                if not line_regex.search(output_lines[start_idx + i]):
                    match = False
                    break
            if match:
                return True
        return False


@dataclass
class PatternPair:
    """Linked ready+busy pattern pair."""

    ready: str
    busy: str


@dataclass
class PatternStore:
    """Load, save, and match patterns."""

    path: Path = field(default_factory=lambda: PATTERNS_PATH)
    patterns: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    _hook_manager: "HookManager | None" = field(default=None, repr=False, init=False)

    def __post_init__(self):
        self.load()

    @property
    def hook_manager(self):
        """Lazy-initialized hook manager."""
        if self._hook_manager is None:
            from .hooks import HookManager

            self._hook_manager = HookManager()
            self._hook_manager.load_from_patterns(self.patterns)
        return self._hook_manager

    def reload_hooks(self):
        """Reload hooks after pattern changes."""
        if self._hook_manager:
            self._hook_manager.load_from_patterns(self.patterns)

    def load(self):
        """Load patterns from YAML file."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self.patterns = yaml.safe_load(f) or {}
            except (yaml.YAMLError, IOError):
                self.patterns = {}
        else:
            self.patterns = {}
        self.reload_hooks()

    def save(self):
        """Save patterns to YAML file (atomic write)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic)
        with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False, suffix=".yaml") as f:
            yaml.safe_dump(self.patterns, f, default_flow_style=False)
            temp_path = Path(f.name)

        temp_path.rename(self.path)
        self.reload_hooks()

    def match(self, process: str, output: str) -> str | None:
        """Find matching pattern, return state.

        Args:
            process: Process name (e.g., "python", "ssh")
            output: Output text to match against

        Returns:
            State name ("ready" or "busy") or None if no match
        """
        state, _ = self.match_with_info(process, output)
        return state

    def match_with_info(self, process: str, output: str) -> tuple[str | None, str | None]:
        """Find matching pattern, return state and matched pattern.

        Args:
            process: Process name (e.g., "python", "ssh")
            output: Output text to match against

        Returns:
            Tuple of (state, matched_pattern) or (None, None) if no match
        """
        if process in ("ssh", "", None):
            return self._match_all_with_info(output)
        return self._match_process_with_info(process, output)

    def _match_process_with_info(self, process: str, output: str) -> tuple[str | None, str | None]:
        """Check patterns for specific process with matched pattern info.

        Args:
            process: Process name
            output: Output text

        Returns:
            Tuple of (state, matched_pattern) or (None, None)
        """
        if process not in self.patterns:
            return (None, None)

        # Check pairs first
        pairs_raw = self.patterns[process].get("pairs", [])
        # Type check: pairs is a list of dicts, not strings
        if isinstance(pairs_raw, list) and pairs_raw and isinstance(pairs_raw[0], dict):
            for pair_dict in pairs_raw:
                if isinstance(pair_dict, dict):
                    ready_pattern = pair_dict.get("ready")
                    if ready_pattern and isinstance(ready_pattern, str):
                        pattern = Pattern(raw=ready_pattern, process=process, state="ready")
                        if pattern.matches(output):
                            return ("ready", ready_pattern)

        # Check standalone patterns
        for state, pattern_list in self.patterns[process].items():
            if state in ("pairs", "hooks"):  # Skip pairs and hooks (config sections, not states)
                continue
            if not isinstance(pattern_list, list):
                continue
            for raw in pattern_list:
                pattern = Pattern(raw=raw, process=process, state=state)
                if pattern.matches(output):
                    return (state, raw)

        return (None, None)

    def _match_all_with_info(self, output: str) -> tuple[str | None, str | None]:
        """Check all patterns with info (for ssh/unknown).

        Args:
            output: Output text

        Returns:
            Tuple of (state, matched_pattern) or (None, None)
        """
        for process in self.patterns:
            state, pattern = self._match_process_with_info(process, output)
            if state:
                return (state, pattern)
        return (None, None)

    def add(self, process: str, pattern: str, state: str):
        """Add pattern.

        Args:
            process: Process name
            pattern: DSL pattern string
            state: State this pattern indicates
        """
        self.patterns.setdefault(process, {}).setdefault(state, []).append(pattern)
        self.save()

    def add_pair(self, process: str, ready: str, busy: str):
        """Add linked ready+busy pattern pair.

        Args:
            process: Process name
            ready: Ready pattern DSL
            busy: Busy pattern DSL
        """
        proc_patterns = self.patterns.setdefault(process, {})
        # Get or create pairs list (typing: list[dict] not list[str])
        if "pairs" not in proc_patterns:
            proc_patterns["pairs"] = []  # type: ignore
        pairs_list = proc_patterns["pairs"]
        # Type narrowing for list operations
        if isinstance(pairs_list, list):
            pairs_list.append({"ready": ready, "busy": busy})  # type: ignore
        self.save()

    def get_pair_for_ready(self, process: str, ready_pattern: str) -> PatternPair | None:
        """Find pair that contains this ready pattern.

        Args:
            process: Process name
            ready_pattern: Ready pattern DSL to search for

        Returns:
            PatternPair if found, None otherwise
        """
        if process not in self.patterns:
            return None

        pairs_raw = self.patterns[process].get("pairs", [])
        # Type check: pairs is a list of dicts
        if isinstance(pairs_raw, list):
            for item in pairs_raw:
                if isinstance(item, dict):
                    ready_val = item.get("ready")
                    busy_val = item.get("busy")
                    if ready_val == ready_pattern and isinstance(ready_val, str) and isinstance(busy_val, str):
                        return PatternPair(ready=ready_val, busy=busy_val)

        return None

    def remove(self, process: str, pattern: str, state: str):
        """Remove pattern.

        Args:
            process: Process name
            pattern: Pattern to remove
            state: State the pattern is under
        """
        if process not in self.patterns:
            return
        if state not in self.patterns[process]:
            return

        self.patterns[process][state] = [p for p in self.patterns[process][state] if p != pattern]

        # Clean up empty structures
        if not self.patterns[process][state]:
            del self.patterns[process][state]
        if not self.patterns[process]:
            del self.patterns[process]

        self.save()

    def remove_pair(self, process: str, ready: str, busy: str):
        """Remove pattern pair.

        Args:
            process: Process name
            ready: Ready pattern DSL
            busy: Busy pattern DSL
        """
        if process not in self.patterns:
            return

        pairs_raw = self.patterns[process].get("pairs", [])
        if not isinstance(pairs_raw, list):
            return

        # Filter out the matching pair
        new_pairs = []
        for item in pairs_raw:
            if isinstance(item, dict):
                if item.get("ready") == ready and item.get("busy") == busy:
                    continue  # Skip this pair
                new_pairs.append(item)

        if new_pairs:
            self.patterns[process]["pairs"] = new_pairs  # type: ignore
        else:
            # Remove empty pairs list
            if "pairs" in self.patterns[process]:
                del self.patterns[process]["pairs"]

        # Clean up empty process
        if not self.patterns[process]:
            del self.patterns[process]

        self.save()

    def get(self, process: str) -> dict[str, list[str]]:
        """Get patterns for a process.

        Args:
            process: Process name

        Returns:
            Dict of state -> pattern list
        """
        return self.patterns.get(process, {})

    def all(self) -> dict[str, dict[str, list[str]]]:
        """Get all patterns.

        Returns:
            Full patterns dict
        """
        return self.patterns

    def get_hooks(self, process: str | None = None) -> dict:
        """Get hooks, optionally filtered by process.

        Args:
            process: Process name to filter by (optional)

        Returns:
            Dict of hooks (all or filtered by process)
        """
        if process:
            hooks = self.patterns.get(process, {}).get("hooks", {})
            return hooks if isinstance(hooks, dict) else {}
        return {p: d.get("hooks", {}) for p, d in self.patterns.items() if isinstance(d.get("hooks"), dict)}

    def update_process_config(self, process: str, config: dict):
        """Update entire process config (patterns + hooks).

        Args:
            process: Process name
            config: Full config dict for the process
        """
        self.patterns[process] = config
        self.save()
