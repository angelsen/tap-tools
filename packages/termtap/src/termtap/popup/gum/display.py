"""Display commands for gum (style, format, log)."""

from typing import List, Optional
from .base import _DisplayCommand


class GumStyle(_DisplayCommand):
    """Styled text display.

    Supports colors, borders, alignment, and text formatting.
    """

    def __init__(
        self,
        text: str,
        # Text formatting
        bold: bool = False,
        italic: bool = False,
        faint: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        # Colors
        foreground: Optional[str] = None,
        background: Optional[str] = None,
        # Layout
        align: str = "left",  # left, center, right
        width: int = 0,
        height: int = 0,
        # Borders and spacing
        border: Optional[str] = None,  # none, normal, rounded, thick, double, hidden
        padding: Optional[str] = None,  # "1" or "1 2" (vertical horizontal)
        margin: Optional[str] = None,  # "1" or "1 2" (vertical horizontal)
        # Style shortcuts
        info: bool = False,  # Blue text
        success: bool = False,  # Green text
        warning: bool = False,  # Yellow text
        error: bool = False,  # Red text
        header: bool = False,  # Bold, centered, bordered
    ):
        """Initialize styled text.

        Args:
            text: Text to display.
            bold: Bold text.
            italic: Italic text.
            faint: Dimmed text.
            underline: Underlined text.
            strikethrough: Strikethrough text.
            foreground: Foreground color (e.g., "12", "#ff0000", "red").
            background: Background color.
            align: Text alignment.
            width: Text width.
            height: Text height.
            border: Border style.
            padding: Internal padding.
            margin: External margin.
            info: Blue info style shortcut.
            success: Green success style shortcut.
            warning: Yellow warning style shortcut.
            error: Red error style shortcut.
            header: Header style shortcut.
        """
        super().__init__("style")
        self.text = text

        # Apply shortcuts
        if header:
            bold = True
            align = "center"
            border = border or "rounded"
            foreground = foreground or "14"
        elif info:
            foreground = foreground or "12"
        elif success:
            foreground = foreground or "10"
        elif warning:
            foreground = foreground or "11"
            bold = True
        elif error:
            foreground = foreground or "9"
            bold = True

        # Store final values
        self.bold = bold
        self.italic = italic
        self.faint = faint
        self.underline = underline
        self.strikethrough = strikethrough
        self.foreground = foreground
        self.background = background
        self.align = align
        self.width = width
        self.height = height
        self.border = border
        self.padding = padding
        self.margin = margin

    def render(self) -> List[str]:
        """Render style command."""
        args = self.build_base_cmd()

        # Add text
        args.append(self.quote(self.text))

        # Text formatting
        if self.bold:
            args.append("--bold")
        if self.italic:
            args.append("--italic")
        if self.faint:
            args.append("--faint")
        if self.underline:
            args.append("--underline")
        if self.strikethrough:
            args.append("--strikethrough")

        # Colors
        if self.foreground:
            args.extend(["--foreground", str(self.foreground)])
        if self.background:
            args.extend(["--background", str(self.background)])

        # Layout
        if self.align != "left":
            args.extend(["--align", self.align])

        if self.width > 0:
            args.extend(["--width", str(self.width)])
        if self.height > 0:
            args.extend(["--height", str(self.height)])

        # Borders and spacing
        if self.border:
            args.extend(["--border", self.border])
        if self.padding:
            args.extend(["--padding", self.quote(self.padding)])
        if self.margin:
            args.extend(["--margin", self.quote(self.margin)])

        return [" ".join(args)]


class GumFormat(_DisplayCommand):
    """Format text with various processors.

    Supports markdown, template, code, and emoji formatting.
    """

    def __init__(
        self,
        text: str,
        type: str = "markdown",  # markdown, template, code, emoji
        theme: str = "pink",  # For markdown
        language: str = "",  # For code
    ):
        """Initialize format command.

        Args:
            text: Text to format.
            type: Format type (markdown, template, code, emoji).
            theme: Markdown theme (for type=markdown).
            language: Programming language (for type=code).
        """
        super().__init__("format")
        self.text = text
        self.type = type
        self.theme = theme
        self.language = language

    def render(self) -> List[str]:
        """Render format command."""
        args = self.build_base_cmd()

        # Format-specific args
        args.extend(["--type", self.type])

        if self.type == "markdown":
            args.extend(["--theme", self.theme])
        elif self.type == "code" and self.language:
            args.extend(["--language", self.language])

        # Use echo to pipe text
        return [f"echo {self.quote(self.text)} | {' '.join(args)}"]


class GumLog(_DisplayCommand):
    """Structured logging output."""

    def __init__(
        self,
        message: str,
        level: str = "info",  # none, debug, info, warn, error, fatal
        prefix: Optional[str] = None,
        time: Optional[str] = None,  # kitchen, ansic, rfc822, etc.
        structured: bool = False,
    ):
        """Initialize log command.

        Args:
            message: Log message.
            level: Log level.
            prefix: Optional prefix before message.
            time: Time format to display.
            structured: Use structured logging format.
        """
        super().__init__("log")
        self.message = message
        self.level = level
        self.prefix = prefix
        self.time = time
        self.structured = structured

    def render(self) -> List[str]:
        """Render log command."""
        args = self.build_base_cmd()

        # Add message
        args.append(self.quote(self.message))

        # Log-specific args
        args.extend(["--level", self.level])

        if self.prefix:
            args.extend(["--prefix", self.quote(self.prefix)])

        if self.time:
            args.extend(["--time", self.time])

        if self.structured:
            args.append("--structured")

        return [" ".join(args)]
