"""Handler package for pattern matching.

PUBLIC API:
  - PatternStore: Load/save/match patterns
  - split_output: Normalize output text into lines for matching
  - dsl_matches: Check a DSL pattern against pre-split output lines
  - compile_dsl: Compile DSL string to regex
  - DSLError: DSL parsing and compilation errors
  - Hook: Single hook configuration
  - HookManager: Check and track hook firing
"""

from .hooks import Hook, HookManager
from .patterns import DSLError, PatternStore, compile_dsl, dsl_matches, split_output

__all__ = ["PatternStore", "split_output", "dsl_matches", "compile_dsl", "DSLError", "Hook", "HookManager"]
