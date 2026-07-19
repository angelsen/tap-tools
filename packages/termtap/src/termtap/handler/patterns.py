"""Pattern storage and matching with DSL support.

PUBLIC API:
  - PatternStore: Load/save/match patterns from YAML
  - split_output: Normalize output text into lines for matching
  - dsl_matches: Check a DSL pattern against pre-split output lines
  - dsl_match_line: Last output line index where a DSL pattern matches
  - compile_dsl: Compile DSL string to regex
  - DSLError: DSL parsing and compilation errors
"""

import re
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from ..paths import PATTERNS_PATH

if TYPE_CHECKING:
    from .hooks import HookManager

__all__ = ["PatternStore", "PatternPair", "split_output", "dsl_matches", "dsl_match_line", "compile_dsl", "DSLError"]


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
            # Convert DSL range (2-4) to regex range {2,4}. More than one
            # hyphen would emit {2,4,6}, which re treats as LITERAL text --
            # silently wrong, so reject it here.
            if spec.count("-") > 1:
                raise DSLError(f"Invalid quantifier '{spec}': use N or N-M")
            return (f"{{{spec.replace('-', ',')}}}", j - pos)
        else:
            return (f"{{{spec}}}", j - pos)  # {4}

    return ("+", 0)  # Default


def _unescape_literal(content: str) -> str:
    """Decode \\\\, \\[ and \\] escapes in literal bracket content."""
    out = []
    k = 0
    while k < len(content):
        if content[k] == "\\" and k + 1 < len(content) and content[k + 1] in "\\[]":
            out.append(content[k + 1])
            k += 2
        else:
            out.append(content[k])
            k += 1
    return "".join(out)


@lru_cache(maxsize=256)
def compile_dsl(dsl: str) -> re.Pattern:
    """Compile DSL string to regex pattern (cached — called per line on the match hot path).

    DSL Syntax:
        Types:      #=digit, w=word, .=any, _=space
        Quants:     +=one+, *=zero+, ?=optional, N=exact, N-M=range
        Anchors:    ^=start, $=end
        Literal:    [text]=exact, [N]=gap, [*]=any, [+]=one+

    Args:
        dsl: DSL pattern string

    Returns:
        Compiled regex pattern

    Raises:
        DSLError: On malformed DSL, or DSL that would compile to a regex
            matching everything (empty pattern) or to an invalid regex
            (e.g. reversed range quantifier)
    """
    if not dsl:
        # Empty DSL compiles to the empty regex, which search()-matches every
        # line -- a pattern that reports every pane as ready forever.
        raise DSLError("Empty pattern")

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
            # Find closing ] that isn't escaped: a ] preceded by an odd
            # number of backslashes is escaped (\\] is an escaped
            # backslash followed by a real closing bracket).
            j = i + 1
            end = None
            while j < len(dsl):
                if dsl[j] == "]":
                    backslashes = 0
                    k = j - 1
                    while k > i and dsl[k] == "\\":
                        backslashes += 1
                        k -= 1
                    if backslashes % 2 == 0:
                        end = j
                        break
                j += 1
            if end is None:
                context_start = max(0, i - 5)
                context_end = min(len(dsl), i + 10)
                raise DSLError(
                    f"Invalid DSL pattern at position {i}: unmatched '[' (context: '{dsl[context_start:context_end]}')"
                )
            content = dsl[i + 1 : end]
            if content == "":
                raise DSLError(f"Invalid DSL pattern at position {i}: empty brackets '[]'")
            if content == "*":
                result.append(".*")
            elif content == "+":
                result.append(".+")
            elif content.isdigit():
                result.append(f".{{{content}}}")  # [31] → .{31}
            else:
                result.append(re.escape(_unescape_literal(content)))
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

    try:
        return re.compile("".join(result))
    except re.error as e:
        # e.g. a reversed range quantifier (#4-2 -> \d{4,2}). Surface as
        # DSLError so write-time validation rejects it and the match loop
        # skips it instead of crashing the feed path.
        raise DSLError(f"Invalid DSL pattern '{dsl}': {e}") from e


def _validate_dsl(pattern: str) -> None:
    """Raise DSLError if any line of the pattern fails to compile.

    Called at write time so a malformed pattern is rejected at the RPC
    edge instead of throwing on the feed hot path forever after.
    """
    for line in pattern.strip().split("\n"):
        compile_dsl(line)


def split_output(output: str) -> list[str]:
    """Normalize output text into lines for matching.

    Strips trailing whitespace from each line to normalize between:
    - tmux capture-pane (strips trailing spaces)
    - pipe-pane stream (preserves trailing spaces)
    """
    return [line.rstrip() for line in output.rstrip("\n").split("\n")]


def dsl_matches(raw: str, output_lines: list[str]) -> bool:
    """Check a DSL pattern (single or multi-line) against pre-split output.

    Single-line: matches if found anywhere.
    Multi-line: matches if consecutive sequence found anywhere.

    Takes pre-split lines so callers matching many patterns against the
    same output (the feed hot path) split once, not once per pattern.

    Args:
        raw: DSL pattern string (may have newlines)
        output_lines: Output lines from split_output()

    Returns:
        True if pattern matches

    Raises:
        DSLError: If the pattern does not compile
    """
    pattern_lines = raw.strip().split("\n")

    if len(output_lines) < len(pattern_lines):
        return False

    if len(pattern_lines) == 1:
        regex = compile_dsl(pattern_lines[0])
        return any(regex.search(line) for line in output_lines)

    regexes = [compile_dsl(line) for line in pattern_lines]
    for start_idx in range(len(output_lines) - len(regexes) + 1):
        if all(regex.search(output_lines[start_idx + i]) for i, regex in enumerate(regexes)):
            return True
    return False


def dsl_match_line(raw: str, output_lines: list[str]) -> int | None:
    """Index of the LAST output line where the pattern matches, or None.

    For a multi-line pattern, the index of the last line of the last
    matching window. Used by auto-pair resolution to compare where the
    busy and ready patterns sit relative to each other.

    Args:
        raw: DSL pattern string (may have newlines)
        output_lines: Output lines from split_output()

    Raises:
        DSLError: If the pattern does not compile
    """
    pattern_lines = raw.strip().split("\n")

    if len(output_lines) < len(pattern_lines):
        return None

    if len(pattern_lines) == 1:
        regex = compile_dsl(pattern_lines[0])
        for idx in range(len(output_lines) - 1, -1, -1):
            if regex.search(output_lines[idx]):
                return idx
        return None

    regexes = [compile_dsl(line) for line in pattern_lines]
    for start_idx in range(len(output_lines) - len(regexes), -1, -1):
        if all(regex.search(output_lines[start_idx + i]) for i, regex in enumerate(regexes)):
            return start_idx + len(regexes) - 1
    return None


@dataclass
class PatternPair:
    """Linked ready+busy pattern pair."""

    ready: str
    busy: str


@dataclass
class PatternStore:
    """Load, save, and match patterns."""

    # Per-process config: state -> list[str] patterns, plus "pairs" (list of
    # dicts) and "hooks" (dict) config sections. YAML-loaded, so values are
    # defensively isinstance-checked where hand-edited input could break.
    path: Path = field(default_factory=lambda: PATTERNS_PATH)
    patterns: dict[str, dict[str, Any]] = field(default_factory=dict)
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
        # Split once here: every stored pattern matches against the same lines
        output_lines = split_output(output)
        if process in ("ssh", "", None):
            for candidate in self.patterns:
                state, pattern = self._match_process(candidate, output_lines)
                if state:
                    return (state, pattern)
            return (None, None)
        return self._match_process(process, output_lines)

    def _match_process(self, process: str, output_lines: list[str]) -> tuple[str | None, str | None]:
        """Check patterns for specific process against pre-split output.

        Priority is explicit, not YAML section order: standalone busy first
        (a line matching both busy and ready must count as busy -- the
        conservative failure mode is waiting, not double-sending), then pair
        ready patterns, then remaining standalone states.

        Args:
            process: Process name
            output_lines: Output lines from split_output()

        Returns:
            Tuple of (state, matched_pattern) or (None, None)
        """
        if process not in self.patterns:
            return (None, None)

        def _match_state(state: str) -> str | None:
            pattern_list = self.patterns[process].get(state)
            if not isinstance(pattern_list, list):
                return None
            for raw in pattern_list:
                try:
                    if dsl_matches(raw, output_lines):
                        return raw
                except DSLError:
                    continue  # hand-edited YAML can hold invalid DSL
            return None

        # 1. Standalone busy
        if raw := _match_state("busy"):
            return ("busy", raw)

        # 2. Pair ready patterns
        pairs_raw = self.patterns[process].get("pairs", [])
        if isinstance(pairs_raw, list):
            for pair_dict in pairs_raw:
                if isinstance(pair_dict, dict):
                    ready_pattern = pair_dict.get("ready")
                    if ready_pattern and isinstance(ready_pattern, str):
                        try:
                            if dsl_matches(ready_pattern, output_lines):
                                return ("ready", ready_pattern)
                        except DSLError:
                            continue  # hand-edited YAML can hold invalid DSL

        # 3. Remaining standalone states (ready and any custom states)
        for state in self.patterns[process]:
            if state in ("busy", "pairs", "hooks"):  # busy done; pairs/hooks are config sections
                continue
            if raw := _match_state(state):
                return (state, raw)

        return (None, None)

    def add(self, process: str, pattern: str, state: str):
        """Add pattern.

        Args:
            process: Process name
            pattern: DSL pattern string
            state: State this pattern indicates

        Raises:
            DSLError: If the pattern does not compile
        """
        _validate_dsl(pattern)
        self.patterns.setdefault(process, {}).setdefault(state, []).append(pattern)
        self.save()

    def add_pair(self, process: str, ready: str, busy: str):
        """Add linked ready+busy pattern pair.

        Args:
            process: Process name
            ready: Ready pattern DSL
            busy: Busy pattern DSL

        Raises:
            DSLError: If either pattern does not compile
        """
        _validate_dsl(ready)
        _validate_dsl(busy)
        pairs = self.patterns.setdefault(process, {}).setdefault("pairs", [])
        if isinstance(pairs, list):
            pairs.append({"ready": ready, "busy": busy})
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
            self.patterns[process]["pairs"] = new_pairs
        else:
            # Remove empty pairs list
            if "pairs" in self.patterns[process]:
                del self.patterns[process]["pairs"]

        # Clean up empty process
        if not self.patterns[process]:
            del self.patterns[process]

        self.save()

    def get(self, process: str) -> dict[str, Any]:
        """Get patterns for a process.

        Args:
            process: Process name

        Returns:
            Dict of state -> pattern list (plus pairs/hooks config sections)
        """
        return self.patterns.get(process, {})

    def all(self) -> dict[str, dict[str, Any]]:
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
