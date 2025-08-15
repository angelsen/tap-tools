"""Canvas manages its total allocated space.

PUBLIC API:
  - Canvas: Container for content elements with layout and styling management
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union
from .core.base import Element
from .core.types import Dimension, BorderStyle, Align
from .core.utils import calculate_content_dimensions

@dataclass
class Canvas(Element):
    """Canvas manages its total allocated space.
    
    Width/height represent TOTAL space including border.
    Canvas is responsible for subtracting border space when needed.
    """
    
    # Total dimensions
    width: Optional[Dimension] = None  # Total space: 80 or "100%"
    height: Optional[Dimension] = None  # Total space: 20 or "50%"
    
    # Visual
    border: BorderStyle = "hidden"
    align: Align = "left"  # Changed from center to avoid gum rendering issues
    padding: Optional[str] = None  # "1 2" for v h
    margin: Optional[str] = None   # "1 2" for v h
    
    # Content
    content: List[Element] = field(default_factory=list)
    
    def add(self, *elements: Element) -> 'Canvas':
        """Add elements to canvas."""
        for element in elements:
            if isinstance(element, Canvas):
                raise ValueError("Canvas cannot contain other Canvas elements")
        self.content.extend(elements)
        return self
    
    def render(self, builder) -> str:
        """Render canvas with content."""
        
        # Use POPUP dimensions (which are the dimensions inside the tmux popup)
        # Canvas gets percentage of POPUP dimensions
        if self.width:
            if isinstance(self.width, str) and self.width.endswith("%"):
                percent = self.width[:-1]
                canvas_total_width = f"$(({percent} * $POPUP_WIDTH / 100))"
            else:
                canvas_total_width = str(self.width)
        else:
            # Default to full popup width
            canvas_total_width = "$POPUP_WIDTH"
        
        # Height calculation
        if self.height:
            if isinstance(self.height, str) and self.height.endswith("%"):
                percent = self.height[:-1]
                canvas_total_height = f"$(({percent} * $POPUP_HEIGHT / 100))"
            else:
                canvas_total_height = str(self.height)
        else:
            canvas_total_height = None
        
        # Render content - two modes: simple and grid
        content_results = []
        from .layout import Row, Column
        
        # Calculate available width for content using our utility
        # This accounts for both border AND margin if canvas has them
        # But for content placement, we only need to account for border
        # (margin affects canvas position, not content within canvas)
        has_real_border = self.border not in ["none", "hidden"]
        
        if has_real_border:
            # Canvas has real border, subtract 2 from width for content
            if canvas_total_width.startswith("$"):
                # Runtime variable
                content_width = f"$(({canvas_total_width} - 2))"
            else:
                # Fixed value
                content_width = str(int(canvas_total_width) - 2) if canvas_total_width.isdigit() else canvas_total_width
        else:
            # No border space needed
            content_width = canvas_total_width
        
        for i, element in enumerate(self.content):
            if isinstance(element, str):
                # Raw string - wrap in Text for consistent handling
                from .content import Text
                element = Text(element)
            
            # Grid mode: Row/Column handle their own layout
            if isinstance(element, (Row, Column)):
                # Grid mode - pass available content width (inside border)
                result = element.render_with_allocation(builder, content_width, canvas_total_height)
                if result:
                    content_results.append(result)
            
            # Simple mode: content elements with optional styling
            else:
                # Check if element has render_with_style (our content elements)
                if hasattr(element, 'render_with_style'):
                    result = element.render_with_style(builder, content_width)
                else:
                    # Fallback for other elements
                    result = element.render_with_allocation(builder, content_width, canvas_total_height)
                if result:
                    content_results.append(result)
        
        if not content_results:
            return ""
        
        # Join content vertically (simple mode stacks, grid mode has rows)
        if len(content_results) > 1:
            joined = builder.add_join(content_results, vertical=True, result_name="CANVAS_CONTENT")
        else:
            joined = content_results[0]
        
        # Apply canvas-level styling if needed
        # Rule: Apply style if we have real border, padding, margin, explicit size, or non-left alignment
        needs_styling = (
            has_real_border or 
            self.padding or 
            self.margin or  # Margin also triggers styling
            self.width or 
            self.height or 
            self.align != "left"
        )
        
        if needs_styling:
            # Calculate dimensions with margin/border adjustments
            styled_width, styled_height = calculate_content_dimensions(
                total_width=canvas_total_width,
                total_height=canvas_total_height,
                border=self.border,
                margin=self.margin,
                padding=self.padding
            )
            
            # Use styled dimensions if we need them
            width_arg = styled_width if (has_real_border or self.width or self.align != "left" or self.margin) else None
            height_arg = styled_height if (has_real_border or self.height or self.margin) else None
            
            return builder.add_style(
                joined,
                width=width_arg,
                height=height_arg,
                border=self.border,  # Builder will handle "none"/"hidden" correctly
                align=self.align,
                padding=self.padding,
                margin=self.margin,  # Pass margin to gum
                result_name="CANVAS_OUTPUT"
            )
        
        # No styling needed - return content as-is
        return joined