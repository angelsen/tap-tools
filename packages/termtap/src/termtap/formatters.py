"""Custom formatters for termtap displays."""

from typing import Any
from replkit2.types.core import CommandMeta
from replkit2.textkit.formatter import TextFormatter

from .app import app


@app.formatter.register("codeblock")  # pyright: ignore[reportAttributeAccessIssue]
def format_codeblock(data: Any, meta: CommandMeta, formatter: TextFormatter) -> str:
    """Format command output as markdown code block.
    
    Expects data dict with:
    - content: The output to display
    - process: Language hint for syntax (optional)
    
    Other fields preserved for programmatic use.
    """
    if isinstance(data, dict) and "content" in data:
        process = data.get("process", "text")
        content = data.get("content", "")
        
        # Handle empty output
        if not content:
            return f"```{process}\n[No output]\n```"
        
        # Strip trailing whitespace but preserve formatting
        content = content.rstrip() if isinstance(content, str) else str(content)
        
        return f"```{process}\n{content}\n```"
    
    # Fallback for non-dict
    return f"```\n{str(data)}\n```"