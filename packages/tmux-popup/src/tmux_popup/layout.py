"""Layout elements with self-managed space.

PUBLIC API:
  - Row: Horizontal layout container for organizing elements side-by-side
  - Column: Vertical layout container for organizing elements top-to-bottom
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union
from .core.base import Element
from .core.utils import calculate_content_dimensions
from .core.types import BorderStyle, Align


@dataclass
class Column(Element):
    """Column manages its total allocated space.

    Width represents TOTAL space including border AND margin.
    Column subtracts border and margin space internally for content.
    """

    elements: List[Union[Element, str]] = field(default_factory=list)
    width: Optional[Union[int, str]] = None  # Total space
    height: Optional[Union[int, str]] = None  # Total space
    border: BorderStyle = "hidden"
    align: Align = "left"
    padding: Optional[str] = None
    margin: Optional[str] = None  # New: margin support

    def __init__(
        self,
        *elements,
        width=None,
        height=None,
        border: BorderStyle = "hidden",
        align: Align = "left",
        padding=None,
        margin=None,
    ):
        """Initialize with elements and properties."""
        self.elements = list(elements)
        self.width = width
        self.height = height
        self.border = border
        self.align = align
        self.padding = padding
        self.margin = margin

    def add(self, *elements) -> "Column":
        """Add more elements."""
        self.elements.extend(elements)
        return self

    def render(self, builder) -> str:
        """Standalone render."""
        return self.render_with_allocation(builder, None, None)

    def render_with_allocation(self, builder, allocated_width=None, allocated_height=None) -> str:
        """Render with allocated space from parent."""
        if not self.elements:
            return ""

        # Use allocated width or our own width
        # Convert int to str if needed
        if allocated_width:
            total_width = allocated_width
        elif self.width:
            total_width = str(self.width)
        else:
            total_width = None

        if allocated_height:
            total_height = allocated_height
        elif self.height:
            total_height = str(self.height)
        else:
            total_height = None

        # Render content
        content_vars = []
        col_index = builder.result_counter

        for i, element in enumerate(self.elements):
            if isinstance(element, str):
                text_var = builder.add_literal(element, f"COL{col_index}_TEXT_{i}")
                content_vars.append(text_var)
            else:
                # All elements support render_with_allocation now
                result = element.render_with_allocation(builder, total_width, total_height)
                if result:
                    content_vars.append(result)

        if not content_vars:
            return ""

        # Join content vertically
        if len(content_vars) > 1:
            content = builder.add_join(content_vars, vertical=True, result_name=f"COL{col_index}_CONTENT")
        else:
            content = content_vars[0]

        # Calculate dimensions for gum style using our utility
        # This handles border AND margin deductions cleanly
        gum_width, gum_height = calculate_content_dimensions(
            total_width=total_width,
            total_height=total_height,
            border=self.border,
            margin=self.margin,
            padding=self.padding,  # Note: padding handled by gum, not deducted
        )

        # Style the column
        return builder.add_style(
            content,
            width=gum_width,
            height=gum_height,
            border=self.border,
            align=self.align,
            padding=self.padding,
            margin=self.margin,  # Pass margin to gum
            result_name=f"COL{col_index}_STYLED",
        )


@dataclass
class Row(Element):
    """Row distributes its available space to children.

    Each child gets a portion of the TOTAL space.
    Children are responsible for their own borders.
    """

    elements: List[Union[Element, str]] = field(default_factory=list)
    align: Align = "left"

    def __init__(self, *elements, align: Align = "left"):
        """Initialize with elements."""
        self.elements = list(elements)
        self.align = align

    def add(self, *elements) -> "Row":
        """Add more elements."""
        self.elements.extend(elements)
        return self

    def render(self, builder) -> str:
        """Standalone render."""
        return self.render_with_allocation(builder, None, None)

    def render_with_allocation(self, builder, allocated_width=None, allocated_height=None) -> str:
        """Render with available space from parent."""
        if not self.elements:
            return ""

        # Base width for calculations - use what parent provides
        # Canvas will pass its width which is already calculated from POPUP_WIDTH
        base_width = allocated_width or "$POPUP_WIDTH"

        # Render each element
        element_vars = []
        row_index = builder.result_counter

        for i, element in enumerate(self.elements):
            if isinstance(element, str):
                text_var = builder.add_literal(element, f"ROW{row_index}_TEXT_{i}")
                element_vars.append(text_var)

            elif isinstance(element, Column):
                # Calculate column's total allocation
                if element.width:
                    if isinstance(element.width, str) and element.width.endswith("%"):
                        # Percentage of available space
                        percent = element.width[:-1]
                        col_width = builder.add_variable(
                            f"COL{i}_TOTAL_WIDTH",
                            f"$(({percent} * {base_width} / 100))",
                            f"Column {i} gets {element.width} of row space",
                        )
                    else:
                        # Fixed width
                        col_width = str(element.width)
                else:
                    # No width specified
                    col_width = None

                # Render column with its allocation
                result = element.render_with_allocation(builder, col_width, allocated_height)
                if result:
                    element_vars.append(result)
            else:
                # Other elements - use uniform interface
                result = element.render_with_allocation(builder, allocated_width, allocated_height)
                if result:
                    element_vars.append(result)

        if not element_vars:
            return ""

        # Join horizontally
        return builder.add_join(element_vars, vertical=False, result_name=f"ROW{row_index}_JOINED")
