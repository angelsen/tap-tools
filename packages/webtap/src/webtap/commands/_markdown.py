"""Markdown extensions and utilities for WebTap commands."""

from replkit2.textkit import MarkdownElement
from webtap.commands._symbols import sym


class Table(MarkdownElement):
    """Markdown table element for structured data display."""

    element_type = "table"

    def __init__(self, headers: list[str], rows: list[dict], align: str = "left"):
        self.headers = headers
        self.rows = rows
        self.align = align

    @classmethod
    def from_dict(cls, data: dict) -> "Table":
        return cls(headers=data.get("headers", []), rows=data.get("rows", []), align=data.get("align", "left"))

    def render(self) -> str:
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
    """Alert/warning element for important messages."""

    element_type = "alert"

    def __init__(self, message: str, level: str = "warning"):
        self.message = message
        self.level = level  # warning, error, info, success

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        return cls(message=data.get("message", ""), level=data.get("level", "warning"))

    def render(self) -> str:
        # Use symbol registry for consistent ASCII symbols
        icon = sym(self.level)
        return f"{icon} **{self.message}**"
