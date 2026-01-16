"""Termtap animated logo text widget.

PUBLIC API:
  - LogoText: Animated ASCII logo text with gradient colors
"""

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual.strip import Strip
from textual_coloromatic import Coloromatic

__all__ = ["LogoText"]


class LogoText(Coloromatic):
    """Animated ASCII logo text.

    Usage:
        yield LogoText(
            LOGO_ASCII,
            colors=["$primary", "$accent"],
            animate=True,
            fps=8
        )
    """

    def __init__(
        self,
        text: str,
        *,
        colors: list[str],
        animate: bool = True,
        fps: int = 8,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialize animated logo text.

        Args:
            text: ASCII art text to display
            colors: Gradient colors (theme variables supported)
            animate: Enable gradient animation
            fps: Animation frames per second
            id: Widget ID (optional)
            classes: CSS classes (optional)
        """
        super().__init__(
            text,
            colors=colors,
            animate=animate,
            fps=fps,
            id=id,
            classes=classes,
        )

    def render_line(self, y: int) -> Strip:
        """Render line with forced background color.

        Overrides Coloromatic to add explicit bgcolor to all segments,
        preventing Textual's CSS background blending from showing through
        on whitespace characters.
        """
        strip = super().render_line(y)

        # Get $surface color from theme (fallback for startup)
        surface_color = self.app.theme_variables.get("surface", "#1e1e1e")

        # Force background on all segments
        new_segments = [
            Segment(seg.text, (seg.style or RichStyle()) + RichStyle(bgcolor=surface_color)) for seg in strip._segments
        ]

        return Strip(new_segments)
