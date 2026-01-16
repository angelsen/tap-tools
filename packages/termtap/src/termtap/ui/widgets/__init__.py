"""Textual widgets for termtap companion app.

PUBLIC API:
  - BaseTerminalPane: Read-only terminal output base
  - OutputPane: Scrollable output with cursor-based selection
  - PatternEditor: Editable DSL pattern editor
  - DslReference: DSL syntax and examples reference
  - PreviewPane: Scrollable preview of pane content
  - FzfItem: NamedTuple(display, value, search) for selector items
  - FzfSelector: FZF-style unified keyboard selector
  - Background: Animated weave background container
  - LogoText: Animated ASCII logo text
"""

from .base import BaseTerminalPane
from .output_pane import OutputPane
from .pattern_editor import PatternEditor
from .preview_pane import PreviewPane
from .fzf_selector import FzfSelector, FzfItem
from .dsl_reference import DslReference
from .background import Background
from .logo_text import LogoText

__all__ = [
    "BaseTerminalPane",
    "OutputPane",
    "PatternEditor",
    "DslReference",
    "PreviewPane",
    "FzfSelector",
    "FzfItem",
    "Background",
    "LogoText",
]
