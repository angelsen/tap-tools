"""Handler package for pattern matching.

PUBLIC API:
  - PatternStore: Load/save/match patterns
  - Pattern: Single pattern definition
  - compile_dsl: Compile DSL string to regex
  - DSLError: DSL parsing and compilation errors
  - Hook: Single hook configuration
  - HookManager: Check and track hook firing
"""

from .hooks import Hook, HookManager
from .patterns import DSLError, Pattern, PatternStore, compile_dsl

__all__ = ["PatternStore", "Pattern", "compile_dsl", "DSLError", "Hook", "HookManager"]
