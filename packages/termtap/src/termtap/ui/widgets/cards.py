"""Card builders using Textual containers.

PUBLIC API:
  - syntax_card: DSL syntax reference
  - example_card: Code example with highlighting
  - pattern_examples_card: Terminal → DSL examples
"""

from textual.containers import Container
from textual.widgets import Static

__all__ = ["syntax_card", "example_card", "pattern_examples_card"]


def syntax_card(title: str = "Pattern Syntax") -> Container:
    """DSL syntax reference card."""
    content = """[bold cyan]^text[/]  starts with     [bold cyan]#+ w+ _+[/]  digit, word, space
[bold cyan]text$[/]  ends with       [bold cyan].+ .* .?[/]  any (one+, zero+, opt)
[bold cyan]^text$[/] exact match     [bold cyan]w5 w2-4[/]   exact count, range
[bold cyan]\\[text][/] literal        [bold cyan]\\[5] \\[*][/]  gap, any, one+"""

    return Container(
        Static(f"[bold]{title}[/]", classes="card-title"),
        Static(content),
        classes="card card-info",
    )


def example_card(title: str, code: str, card_class: str = "card-info") -> Container:
    """Code example card."""
    return Container(
        Static(f"[bold]{title}[/]", classes="card-title"),
        Static(code),
        classes=f"card {card_class}",
    )


def pattern_examples_card(title: str, examples: list[tuple[str, str]], card_class: str) -> Container:
    """Pattern examples card (terminal output + DSL)."""
    lines = [f"[dim]{term}[/]  →  [bold cyan]{pattern}[/]" for term, pattern in examples]

    return Container(
        Static(f"[bold]{title}[/]", classes="card-title"),
        Static("\n".join(lines)),
        classes=f"card {card_class}",
    )
