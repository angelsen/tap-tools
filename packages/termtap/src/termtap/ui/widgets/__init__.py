"""Textual widgets for termtap companion app.

PUBLIC API:
  - OutputPane: Scrollable output with cursor-based selection
  - PatternEditor: Editable DSL pattern editor
  - DslReference: DSL syntax and examples reference
  - PreviewPane: Scrollable preview of pane content
  - FzfItem: NamedTuple(display, value, search) for selector items
  - FzfSelector: FZF-style unified keyboard selector
"""

from .output_pane import OutputPane
from .build_preview import PatternEditor
from .preview_pane import PreviewPane
from .fzf_selector import FzfSelector, FzfItem
from .dsl_reference import DslReference

__all__ = [
    "OutputPane",
    "PatternEditor",
    "DslReference",
    "PreviewPane",
    "FzfSelector",
    "FzfItem",
]
