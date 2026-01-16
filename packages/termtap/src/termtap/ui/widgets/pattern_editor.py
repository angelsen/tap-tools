"""Pattern editor widget for DSL pattern building.

PUBLIC API:
  - PatternEditor: Editable TextArea for DSL patterns
  - PatternEntry: Entry with text and position
  - PatternState: Collection of entries (source of truth)
  - ValidationState: Three-state validation enum
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from textual.reactive import reactive
from textual.widgets import TextArea

__all__ = ["PatternEditor", "PatternEntry", "PatternState", "ValidationState"]


@dataclass
class PatternEntry:
    """A literal text entry with position information from output pane."""

    text: str
    row: int
    col: int

    @property
    def end_col(self) -> int:
        return self.col + len(self.text)


@dataclass
class PatternState:
    """Source of truth for pattern building.

    Entries stay in insertion order for chronological undo.
    Use sorted_entries() for position-ordered DSL generation.
    """

    entries: list[PatternEntry] = field(default_factory=list)

    def add_entry(self, text: str, row: int, col: int) -> None:
        self.entries.append(PatternEntry(text, row, col))

    def pop_entry(self) -> PatternEntry | None:
        """Undo: remove last added entry (chronological)."""
        return self.entries.pop() if self.entries else None

    def sorted_entries(self) -> list[PatternEntry]:
        """Get entries sorted by position for DSL generation."""
        return sorted(self.entries, key=lambda e: (e.row, e.col))

    def clear(self) -> None:
        self.entries.clear()


class ValidationState(Enum):
    """Three-state validation for pattern editor."""

    MATCHES = "matches"  # Green: DSL matches entries exactly
    DIVERGED = "diverged"  # Cyan: Valid DSL but user edited
    INVALID = "invalid"  # Auto-rebuild: DSL won't compile


def _escape_literal(text: str) -> str:
    """Escape brackets in literal text."""
    return text.replace("[", "\\[").replace("]", "\\]")


def _unescape_literal(text: str) -> str:
    """Unescape brackets in literal text."""
    return text.replace("\\[", "[").replace("\\]", "]")


def generate_dsl(state: PatternState) -> str:
    """Generate DSL from entries with exact gaps.

    Uses sorted_entries() for position order.
    Groups by row, calculates gaps, emits [N] and [text].
    Does NOT add anchors - caller handles those.
    """
    if not state.entries:
        return ""

    entries = state.sorted_entries()
    rows: dict[int, list[PatternEntry]] = {}
    for entry in entries:
        rows.setdefault(entry.row, []).append(entry)

    sorted_rows = sorted(rows.keys())
    lines = []

    for row in sorted_rows:
        row_entries = rows[row]  # Already sorted by add order within row
        row_entries.sort(key=lambda e: e.col)  # Sort by column
        line_parts = []
        prev_end = 0

        for entry in row_entries:
            gap = entry.col - prev_end
            if gap > 0:
                line_parts.append(f"[{gap}]")
            line_parts.append(f"[{_escape_literal(entry.text)}]")
            prev_end = entry.end_col

        lines.append("".join(line_parts))

    return "\n".join(lines)


def parse_dsl_literals(dsl: str) -> list[str]:
    """Extract literal contents from DSL.

    Literals are [text] where text is NOT:
    - A single number or range (gap exact)
    - * or + (gap wildcards)
    """
    literals = []
    i = 0

    while i < len(dsl):
        if dsl[i] == "[":
            j = i + 1
            while j < len(dsl):
                if dsl[j] == "]" and (j == i + 1 or dsl[j - 1] != "\\"):
                    break
                j += 1

            if j < len(dsl):
                content = dsl[i + 1 : j]
                if not _is_gap_content(content):
                    literals.append(_unescape_literal(content))
            i = j + 1
        else:
            i += 1

    return literals


def _is_gap_content(content: str) -> bool:
    """Check if bracket content is a gap (not a literal)."""
    if content in ("*", "+"):
        return True
    if re.fullmatch(r"\d+(-\d+)?", content):
        return True
    return False


def _try_compile_dsl(dsl: str) -> bool:
    """Try to compile DSL, return True if valid."""
    from termtap.handler.patterns import compile_dsl

    try:
        for line in dsl.strip().split("\n"):
            line = line.lstrip("^").rstrip("$")
            if line:
                compile_dsl(line)
        return True
    except Exception:
        return False


def validate_dsl(dsl: str, state: PatternState) -> ValidationState:
    """Determine validation state.

    MATCHES: DSL exactly equals what would be generated from entries (+ anchors)
    DIVERGED: DSL compiles but differs from generated (user edited)
    INVALID: DSL won't compile
    """
    if not state.entries:
        return ValidationState.MATCHES

    if not _try_compile_dsl(dsl):
        return ValidationState.INVALID

    # Compare against regenerated DSL (ignoring anchors)
    generated = generate_dsl(state)
    current = dsl.lstrip("^").rstrip("$")

    if current == generated:
        return ValidationState.MATCHES

    return ValidationState.DIVERGED


class PatternEditor(TextArea):
    """Editable DSL pattern editor with entries-based validation."""

    validation_state: reactive[ValidationState] = reactive(ValidationState.MATCHES)

    def __init__(self):
        super().__init__("", id="pattern-editor")
        self.show_line_numbers = False
        self._state = PatternState()
        self._rebuilding = False  # Prevent recursive rebuild

    @property
    def state(self) -> PatternState:
        return self._state

    def add_entry(self, text: str, row: int, col: int) -> None:
        """Add entry and rebuild DSL."""
        has_start = self.text.startswith("^")
        has_end = self.text.rstrip().endswith("$")
        self._state.add_entry(text, row, col)
        self._rebuild_dsl(start_anchor=has_start, end_anchor=has_end)

    def undo_entry(self) -> bool:
        """Remove last added entry (chronological). Returns True if removed."""
        has_start = self.text.startswith("^")
        has_end = self.text.rstrip().endswith("$")
        if self._state.pop_entry():
            self._rebuild_dsl(start_anchor=has_start, end_anchor=has_end)
            return True
        return False

    def _rebuild_dsl(self, start_anchor: bool = False, end_anchor: bool = True) -> None:
        """Regenerate DSL from entries with anchors."""
        self._rebuilding = True
        try:
            dsl = generate_dsl(self._state)
            if start_anchor:
                dsl = "^" + dsl
            if end_anchor and dsl:
                dsl = dsl + "$"
            self.text = dsl
            self._update_validation()
        finally:
            self._rebuilding = False

    def _update_validation(self) -> None:
        """Update validation state and CSS classes."""
        state = validate_dsl(self.text, self._state)
        self.validation_state = state

        self.remove_class("-matches", "-diverged", "-invalid")
        if state == ValidationState.MATCHES:
            self.add_class("-matches")
        elif state == ValidationState.DIVERGED:
            self.add_class("-diverged")
        else:
            # Invalid - auto-rebuild (but not if already rebuilding)
            if not self._rebuilding:
                self._auto_rebuild()

    def _auto_rebuild(self) -> None:
        """Auto-rebuild on invalid DSL."""
        has_start = self.text.startswith("^")
        has_end = self.text.rstrip().endswith("$")
        self._rebuild_dsl(start_anchor=has_start, end_anchor=has_end)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle manual edits - validate and auto-rebuild if invalid."""
        if not self._rebuilding:
            self._update_validation()

    def get_pattern(self) -> str:
        """Get current pattern text."""
        return self.text.strip()

    def clear_pattern(self) -> None:
        """Clear the pattern and entries."""
        self._state.clear()
        self._rebuilding = True
        try:
            self.text = ""
            self._update_validation()
        finally:
            self._rebuilding = False
