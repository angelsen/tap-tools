"""Data inspection command for cached results."""

import json
import sys
import ast
from io import StringIO
from typing import Any, Tuple

from webtap.app import app


def _execute_with_result(code: str, namespace: dict) -> Tuple[Any, str]:
    """
    Execute Python code and capture both stdout and the last expression result.
    
    This mimics Jupyter's execution model:
    - All statements are executed
    - The last expression's value is returned
    - stdout is captured
    
    Args:
        code: Python code to execute
        namespace: Dict of variables available to the code
        
    Returns:
        Tuple of (result, stdout_output)
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    result = None
    
    try:
        # Parse the code to find if last node is an expression
        tree = ast.parse(code)
        if tree.body:
            # If last node is an Expression, evaluate it separately
            if isinstance(tree.body[-1], ast.Expr):
                # Execute all but the last node
                if len(tree.body) > 1:
                    exec_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
                    exec(compile(exec_tree, '<string>', 'exec'), namespace)
                # Evaluate the last expression
                result = eval(compile(ast.Expression(body=tree.body[-1].value), '<string>', 'eval'), namespace)
            else:
                # All statements, just exec everything
                exec(compile(tree, '<string>', 'exec'), namespace)
        
    except SyntaxError:
        # Fallback to simple exec if parsing fails
        exec(code, namespace)
    finally:
        # Always restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
    
    return result, output


@app.command()
def inspect(state, expr: str | None = None, **kwargs):
    """
    Inspect cached data with Python expressions.
    
    Full Python access for debugging. The cached data is available as 'data'.
    
    Args:
        expr: Python expression to evaluate
        **kwargs: Cache type and ID (e.g., request="r1")
    
    Examples:
        # After running requests({"headers": "*"})
        inspect(request="r1")                           # Show full data
        inspect(request="r1", expr="list(data.keys())") # Show field names
        
        # Parse JSON headers
        inspect(request="r1", expr="import json; json.loads(data['params.response.headers'])['content-type']")
        
        # Extract with regex
        inspect(request="r2", expr="import re; re.findall(r'session=(\\w+)', data['params.response.headers'])")
        
        # Decode base64
        inspect(request="r1", expr="__import__('base64').b64decode(data['params.body'])")
        
        # Complex analysis
        inspect(request="r1", expr="import json; len(json.loads(data['params.response.headers']))")
    
    Returns:
        Evaluation result or cached data
    """
    # Find which cache to use
    cache_type = None
    cache_id = None
    
    for key, value in kwargs.items():
        if key in state.cache and value:
            cache_type = key
            cache_id = value
            break
    
    if not cache_type:
        available = [k for k in state.cache.keys() if state.cache[k]]
        if available:
            sample_ids = list(state.cache[available[0]].keys())[:3]
            return f"Usage: inspect({available[0]}='id'), e.g., inspect({available[0]}='{sample_ids[0] if sample_ids else 'r1'}')"
        return "No cached data. Run requests() first to cache network data."
    
    # Get from appropriate cache
    data = state.cache[cache_type].get(cache_id)
    if not data:
        cached_ids = list(state.cache[cache_type].keys())
        if cached_ids:
            # Show first 10 available IDs
            show_ids = cached_ids[:10]
            msg = f"ID '{cache_id}' not found. Available in {cache_type} cache: {show_ids}"
            if len(cached_ids) > 10:
                msg += f" ... ({len(cached_ids)} total)"
            return msg
        return f"No data in {cache_type} cache. Run requests() first."
    
    # No expression: show the raw data
    if not expr:
        # Pretty display of the cached data
        output = []
        for field, value in data.items():
            if isinstance(value, str) and len(value) > 500:
                output.append(f"{field}:\n{value[:500]}...\n[truncated, {len(value)} chars total]")
            else:
                output.append(f"{field}:\n{value}")
        return "\n".join(output)
    
    # Execute code with data available (Jupyter-style)
    try:
        # Create namespace with data
        namespace = {"data": data}
        
        # Execute and get result + output
        result, output = _execute_with_result(expr, namespace)
        
        # Combine output and result
        parts = []
        if output:
            parts.append(output.rstrip())
        if result is not None:
            if isinstance(result, (dict, list)):
                formatted = json.dumps(result, indent=2)
                if len(formatted) > 2000:
                    parts.append(formatted[:2000] + f"\n... [truncated, {len(formatted)} chars total]")
                else:
                    parts.append(formatted)
            elif isinstance(result, str) and len(result) > 2000:
                parts.append(result[:2000] + f"\n... [truncated, {len(result)} chars total]")
            else:
                parts.append(str(result))
        
        return '\n'.join(parts) if parts else "(no output)"
            
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}\n\nThe cached data is available as 'data' dict."


@app.command()
def cache_list(state, cache_type: str | None = None):
    """
    List cached items.
    
    Args:
        cache_type: Specific cache to list (request/console/storage)
    
    Examples:
        cache_list()           # Show all caches
        cache_list("request")  # Show request cache
    
    Returns:
        List of cached IDs with previews
    """
    if cache_type:
        if cache_type not in state.cache:
            return f"Unknown cache type: {cache_type}. Available: {list(state.cache.keys())}"
        items = state.cache[cache_type]
        if items:
            # Show first few items with preview
            previews = []
            for id, data in list(items.items())[:10]:
                field = list(data.keys())[0] if data else "empty"
                value_preview = str(list(data.values())[0])[:50] if data else ""
                previews.append(f"  {id}: {field} = {value_preview}...")
            result = f"{cache_type} cache ({len(items)} items):\n" + "\n".join(previews)
            if len(items) > 10:
                result += f"\n  ... and {len(items) - 10} more"
            return result
        return f"{cache_type} cache: empty"
    
    # Show all caches
    result = []
    for name, items in state.cache.items():
        count = len(items)
        if items:
            ids = list(items.keys())[:5]
            result.append(f"{name}: {ids}{'...' if count > 5 else ''} ({count} items)")
        else:
            result.append(f"{name}: empty")
    return "\n".join(result)


@app.command()
def cache_clear(state, cache_type: str = "request"):
    """
    Clear specific cache.
    
    Args:
        cache_type: Cache to clear (default: request)
    
    Examples:
        cache_clear()           # Clear request cache
        cache_clear("console")  # Clear console cache
    
    Returns:
        Confirmation message
    """
    if cache_type not in state.cache:
        return f"Unknown cache type: {cache_type}. Available: {list(state.cache.keys())}"
    
    count = len(state.cache[cache_type])
    state.cache_clear(cache_type)
    return f"Cleared {cache_type} cache ({count} items)"