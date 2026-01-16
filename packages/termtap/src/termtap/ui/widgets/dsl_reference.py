"""DSL reference widget with compact examples.

PUBLIC API:
  - DslReference: Composite widget showing side-by-side pattern examples
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical

from .cards import syntax_card, pattern_examples_card

__all__ = ["DslReference"]


class DslReference(Vertical):
    """Compact DSL examples with side-by-side pattern cards."""

    def compose(self) -> ComposeResult:
        """Compose side-by-side pattern cards + syntax reference."""
        # Ready patterns examples
        ready_examples = [
            ("$", "$"),
            (">>> ", "^[>>>]"),
            ("user@host:~$ ", "[$ ]$"),
        ]

        # Busy patterns examples
        busy_examples = [
            ("Serving HTTP on 0.0.0.0:8000", "[Serving HTTP on ].+"),
            ("VITE v5.0.0 ready in 234ms", "[VITE].+[ready]"),
            ("Installing dependencies...", "^Installing"),
        ]

        # Side-by-side pattern cards (50% each) - styled in companion.tcss
        with Horizontal(id="pattern-cards-row"):
            yield pattern_examples_card("Ready Patterns", ready_examples, "card-success")
            yield pattern_examples_card("Busy Patterns", busy_examples, "card-warning")

        # Syntax reference below (full width)
        yield syntax_card()
