"""Browser element selection and prompt analysis commands.

PUBLIC API:
  - browser: Analyze browser element selections with prompt
"""

from webtap.app import app
from webtap.commands._utils import evaluate_expression, format_expression_result
from webtap.commands._builders import error_response
from webtap.commands._tips import get_tips


@app.command(
    display="markdown",
    fastmcp=[{"type": "resource", "mime_type": "application/json"}, {"type": "tool"}],
)
def selections(state, expr: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Browser element selections with prompt and analysis.

    As Resource (no parameters):
        browser             # Returns current prompt and all selections

    As Tool (with parameters):
        browser(expr="data['prompt']")                          # Get prompt text
        browser(expr="data['selections']['1']['styles']")       # Get styles for #1
        browser(expr="len(data['selections'])")                 # Count selections
        browser(expr="{k: v['selector'] for k, v in data['selections'].items()}")  # All selectors

    Args:
        expr: Python expression with 'data' variable containing prompt and selections

    Returns:
        Formatted browser data or expression result
    """
    # Check if browser data exists
    if not hasattr(state, "browser_data") or not state.browser_data:
        return error_response(
            "No browser selections available",
            suggestions=[
                "Use the Chrome extension to select elements",
                "Click 'Start Selection Mode' in the extension side panel",
                "Select elements on the page",
            ],
        )

    data = state.browser_data

    # No expression - RESOURCE MODE: Return formatted view
    if not expr:
        return _format_browser_data(data)

    # TOOL MODE: Evaluate expression
    try:
        namespace = {"data": data}
        result, output = evaluate_expression(expr, namespace)
        formatted_result = format_expression_result(result, output)

        # Build markdown response
        return {
            "elements": [
                {"type": "heading", "content": "Expression Result", "level": 2},
                {"type": "code_block", "content": expr, "language": "python"},
                {"type": "text", "content": "**Result:**"},
                {"type": "code_block", "content": formatted_result, "language": ""},
            ]
        }
    except Exception as e:
        # Provide helpful suggestions
        suggestions = [
            "The data is available as 'data' variable",
            "Access prompt: data['prompt']",
            "Access selections: data['selections']",
            "Access specific element: data['selections']['1']",
            "Available fields: outerHTML, selector, jsPath, styles, xpath, fullXpath, preview",
        ]

        if "KeyError" in str(type(e).__name__):
            suggestions.extend(
                [
                    "Check available selection IDs: list(data['selections'].keys())",
                    "Check available fields: data['selections']['1'].keys()",
                ]
            )

        return error_response(f"{type(e).__name__}: {e}", suggestions=suggestions)


def _format_browser_data(data: dict) -> dict:
    """Format browser data as markdown for resource view."""
    elements = []

    # Show prompt
    elements.append({"type": "heading", "content": "Browser Prompt", "level": 2})
    elements.append({"type": "text", "content": data.get("prompt", "")})

    # Show selection count
    selection_count = len(data.get("selections", {}))
    elements.append({"type": "text", "content": f"\n**Selected Elements:** {selection_count}"})

    # Show each selection with preview
    if selection_count > 0:
        elements.append({"type": "heading", "content": "Element Selections", "level": 3})

        for sel_id in sorted(data["selections"].keys(), key=lambda x: int(x)):
            sel = data["selections"][sel_id]
            preview = sel.get("preview", {})

            # Build preview line
            preview_parts = [f"**#{sel_id}:**", preview.get("tag", "unknown")]
            if preview.get("id"):
                preview_parts.append(f"#{preview['id']}")
            if preview.get("classes"):
                preview_parts.append(f".{preview['classes'][0]}")

            elements.append({"type": "text", "content": " ".join(preview_parts)})

            # Show selector
            elements.append({"type": "code_block", "content": sel.get("selector", ""), "language": "css"})

        # Show usage tips from TIPS.md
        tips = get_tips("selections")
        if tips:
            elements.append({"type": "heading", "content": "Next Steps", "level": 3})
            elements.append({"type": "list", "items": tips})

    return {"elements": elements}


__all__ = ["selections"]
