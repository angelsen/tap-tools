"""Termtap animated background widget.

PUBLIC API:
  - Background: Animated weave container (wraps children with solid backgrounds)
"""

from textual_coloromatic import Coloromatic

from ..tokens import COLOR_BG_DIM, COLOR_BG_BRIGHT

__all__ = ["Background"]


class Background(Coloromatic):
    """Animated weave container. Children appear as cards over animation.

    Usage:
        with Background(dim=False):
            with Vertical(classes="content-card"):
                yield Static("Content")
    """

    def __init__(self, *, dim: bool = False, id: str | None = None, classes: str | None = None):
        """Initialize animated container.

        Args:
            dim: Use dim/subtle colors (default: False)
            id: Widget ID (default: "background")
            classes: CSS classes
        """
        bg_colors = COLOR_BG_DIM if dim else COLOR_BG_BRIGHT

        super().__init__(
            repeat=True,
            pattern="weave",
            colors=bg_colors,
            animate=False,
            animation_type="gradient",
            horizontal=True,
            fps=4,
            id=id or "background",
            classes=classes,
        )
