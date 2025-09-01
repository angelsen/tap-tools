"""Markdown extensions and utilities for WebTap commands.

This internal module provides specialized markdown elements for displaying structured data
in WebTap commands, including tables and alerts with proper formatting.
"""

from replkit2.textkit import MarkdownElement
from webtap.commands._symbols import sym


class Table(MarkdownElement):
    """Markdown table element for structured data display.

    Creates properly formatted markdown tables with configurable alignment
    and automatic column width calculation based on content.

    Attributes:
        headers: List of column header names.
        rows: List of dictionaries representing table data.
        align: Text alignment for columns (left, right, center).
        element_type: Element type identifier for replkit2.
    """

    element_type = "table"

    def __init__(self, headers: list[str], rows: list[dict], align: str = "left"):
        """Initialize table with headers, data, and alignment.

        Args:
            headers: List of column header names.
            rows: List of dictionaries with data for each row.
            align: Column alignment. Defaults to "left".
        """
        self.headers = headers
        self.rows = rows
        self.align = align

    @classmethod
    def from_dict(cls, data: dict) -> "Table":
        """Create Table instance from dictionary data.

        Args:
            data: Dictionary containing headers, rows, and optional align.

        Returns:
            Table instance with specified configuration.
        """
        return cls(headers=data.get("headers", []), rows=data.get("rows", []), align=data.get("align", "left"))

    def render(self) -> str:
        """Render table as markdown text with proper formatting.

        Returns:
            Markdown-formatted table string with aligned columns.
        """
        if not self.headers:
            return ""

        # Calculate maximum width for each column
        col_widths = []
        for i, header in enumerate(self.headers):
            # Start with header width
            max_width = len(header)
            # Check all row values for this column
            for row in self.rows:
                value = str(row.get(header, ""))
                max_width = max(max_width, len(value))
            col_widths.append(max_width)

        lines = []

        # Header with padding
        padded_headers = []
        for header, width in zip(self.headers, col_widths):
            if self.align == "right":
                padded_headers.append(header.rjust(width))
            elif self.align == "center":
                padded_headers.append(header.center(width))
            else:  # left
                padded_headers.append(header.ljust(width))
        lines.append("| " + " | ".join(padded_headers) + " |")

        # Separator with proper width
        sep = []
        for width in col_widths:
            if self.align == "right":
                sep.append("-" * (width + 1) + ":")
            elif self.align == "center":
                sep.append(":" + "-" * width + ":")
            else:  # left
                sep.append(":" + "-" * (width + 1))
        lines.append("|" + "|".join(sep) + "|")

        # Rows with padding
        for row in self.rows:
            padded_values = []
            for header, width in zip(self.headers, col_widths):
                value = str(row.get(header, ""))
                if self.align == "right":
                    padded_values.append(value.rjust(width))
                elif self.align == "center":
                    padded_values.append(value.center(width))
                else:  # left
                    padded_values.append(value.ljust(width))
            lines.append("| " + " | ".join(padded_values) + " |")

        return "\n".join(lines)


class Alert(MarkdownElement):
    """Alert/warning element for important messages.

    Creates styled alert messages with appropriate icons and formatting
    for different severity levels.

    Attributes:
        message: Alert message text.
        level: Alert severity level (warning, error, info, success).
        element_type: Element type identifier for replkit2.
    """

    element_type = "alert"

    def __init__(self, message: str, level: str = "warning"):
        """Initialize alert with message and severity level.

        Args:
            message: Alert message text to display.
            level: Severity level. Defaults to "warning".
        """
        self.message = message
        self.level = level

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        """Create Alert instance from dictionary data.

        Args:
            data: Dictionary containing message and optional level.

        Returns:
            Alert instance with specified configuration.
        """
        return cls(message=data.get("message", ""), level=data.get("level", "warning"))

    def render(self) -> str:
        """Render alert as markdown text with appropriate icon.

        Returns:
            Markdown-formatted alert string with icon and bold message.
        """
        icon = sym(self.level)
        return f"{icon} **{self.message}**"
