"""Pattern storage and matching with DSL support.

PUBLIC API:
  - PatternStore: Load/save/match patterns from YAML
  - Pattern: Single or multi-line pattern with DSL
  - compile_dsl: Compile DSL string to regex
"""

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..paths import PATTERNS_PATH

__all__ = ["PatternStore", "Pattern", "compile_dsl"]


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
            end = dsl.index("]", i)
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
class PatternStore:
    """Load, save, and match patterns."""

    path: Path = field(default_factory=lambda: PATTERNS_PATH)
    patterns: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def __post_init__(self):
        self.load()

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

    def save(self):
        """Save patterns to YAML file (atomic write)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic)
        with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False, suffix=".yaml") as f:
            yaml.safe_dump(self.patterns, f, default_flow_style=False)
            temp_path = Path(f.name)

        temp_path.rename(self.path)

    def match(self, process: str, output: str) -> str | None:
        """Find matching pattern, return state.

        Args:
            process: Process name (e.g., "python", "ssh")
            output: Output text to match against

        Returns:
            State name ("ready" or "busy") or None if no match
        """
        if process in ("ssh", "", None):
            return self._match_all(output)
        return self._match_process(process, output)

    def _match_process(self, process: str, output: str) -> str | None:
        """Check patterns for specific process.

        Args:
            process: Process name
            output: Output text

        Returns:
            State if matched, None otherwise
        """
        if process not in self.patterns:
            return None

        for state, pattern_list in self.patterns[process].items():
            for raw in pattern_list:
                pattern = Pattern(raw=raw, process=process, state=state)
                if pattern.matches(output):
                    return state
        return None

    def _match_all(self, output: str) -> str | None:
        """Check all patterns (for ssh/unknown).

        Args:
            output: Output text

        Returns:
            State if matched, None otherwise
        """
        for process in self.patterns:
            if result := self._match_process(process, output):
                return result
        return None

    def add(self, process: str, pattern: str, state: str):
        """Add pattern.

        Args:
            process: Process name
            pattern: DSL pattern string
            state: State this pattern indicates
        """
        self.patterns.setdefault(process, {}).setdefault(state, []).append(pattern)
        self.save()

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
