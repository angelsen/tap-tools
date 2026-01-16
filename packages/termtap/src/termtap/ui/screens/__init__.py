"""Textual screens for termtap companion app.

PUBLIC API:
  - QueueScreen: Home screen showing pending actions
  - PaneSelectScreen: Select pane(s) from available panes
  - PatternScreen: Mark patterns for state detection
  - PatternListScreen: View and manage learned patterns
  - PatternEditorScreen: Mini YAML editor for pattern config
  - DslSyntaxScreen: Full DSL syntax reference
"""

from .dsl_syntax_screen import DslSyntaxScreen
from .pane_select_screen import PaneSelectScreen
from .pattern_editor_screen import PatternEditorScreen
from .pattern_list_screen import PatternListScreen
from .pattern_screen import PatternScreen
from .queue_screen import QueueScreen

__all__ = [
    "QueueScreen",
    "PaneSelectScreen",
    "PatternScreen",
    "PatternListScreen",
    "PatternEditorScreen",
    "DslSyntaxScreen",
]
