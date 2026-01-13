"""Handler package for pattern matching.

PUBLIC API:
  - PatternStore: Load/save/match patterns
  - Pattern: Single pattern definition
  - compile_dsl: Compile DSL string to regex
"""

from .patterns import PatternStore, Pattern, compile_dsl

__all__ = ["PatternStore", "Pattern", "compile_dsl"]
