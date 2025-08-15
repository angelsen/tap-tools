"""Content elements for Canvas that render inline.

PUBLIC API:
  - Text: Plain text element with optional styling
  - Markdown: Formatted markdown content
"""

from dataclasses import dataclass
from typing import Optional
from .core.base import Element
from .core.types import Dimension, BorderStyle, Align
from .core.utils import calculate_content_dimensions


@dataclass
class Markdown(Element):
    """Markdown content that formats inline in the canvas."""

    content: str
    theme: str = "pink"
    # Styling properties for simple mode
    width: Optional[Dimension] = None
    border: BorderStyle = "hidden"
    align: Align = "left"
    padding: Optional[str] = None
    margin: Optional[str] = None

    def render(self, builder) -> str:
        """Render markdown by capturing formatted output."""
        # Capture markdown output in a variable
        var_name = f"MARKDOWN_{builder.result_counter}"
        builder.result_counter += 1
        builder.commands.append(f"""{var_name}=$(cat << 'EOF' | gum format --type markdown --theme {self.theme}
{self.content}
EOF
)""")
        return var_name

    def render_with_style(self, builder, available_width=None) -> str:
        """Render with styling for simple canvas mode."""
        # Get the formatted content
        content_var = self.render(builder)

        # Apply styling if any properties are set
        if self.width or self.border != "hidden" or self.padding or self.margin:
            # Calculate width from percentage if needed
            if self.width:
                if isinstance(self.width, str) and self.width.endswith("%"):
                    percent = self.width[:-1]
                    total_width = f"$(({percent} * $POPUP_WIDTH / 100))"
                else:
                    total_width = str(self.width)
            else:
                total_width = available_width  # Use what parent provides

            # Calculate content dimensions with margin/border adjustments
            content_width, _ = calculate_content_dimensions(
                total_width=total_width, total_height=None, border=self.border, margin=self.margin, padding=self.padding
            )

            # Style it
            styled_var = f"STYLED_{builder.result_counter}"
            builder.result_counter += 1
            return builder.add_style(
                content_var,
                width=content_width,
                border=self.border,
                align=self.align,
                padding=self.padding,
                margin=self.margin,
                result_name=styled_var,
            )

        return content_var


@dataclass
class Text(Element):
    """Plain text element."""

    text: str
    # Styling properties for simple mode
    width: Optional[Dimension] = None
    border: BorderStyle = "hidden"
    align: Align = "left"
    padding: Optional[str] = None
    margin: Optional[str] = None

    def render(self, builder) -> str:
        """Render plain text."""
        return builder.add_literal(self.text)

    def render_with_style(self, builder, available_width=None) -> str:
        """Render with styling for simple canvas mode."""
        content_var = self.render(builder)

        if self.width or self.border != "hidden" or self.padding or self.margin:
            # Calculate width from percentage if needed
            if self.width:
                if isinstance(self.width, str) and self.width.endswith("%"):
                    percent = self.width[:-1]
                    total_width = f"$(({percent} * $POPUP_WIDTH / 100))"
                else:
                    total_width = str(self.width)
            else:
                total_width = available_width

            # Calculate content dimensions with adjustments
            content_width, _ = calculate_content_dimensions(
                total_width=total_width, total_height=None, border=self.border, margin=self.margin, padding=self.padding
            )

            styled_var = f"STYLED_{builder.result_counter}"
            builder.result_counter += 1
            return builder.add_style(
                content_var,
                width=content_width,
                border=self.border,
                align=self.align,
                padding=self.padding,
                margin=self.margin,
                result_name=styled_var,
            )

        return content_var
