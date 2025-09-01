"""Shared utilities for WebTap command modules.

Provides formatting, evaluation, and response building utilities used across
command modules for consistent output formatting and data processing.

PUBLIC API:
  - evaluate_expression: Execute Python code with result capture
  - format_expression_result: Format evaluation results for display
  - truncate_string: Truncate strings with ellipsis
  - format_size: Format byte sizes as human-readable strings
  - format_id: Format ID strings with optional truncation
  - process_events_query_results: Process CDP event query results
  - build_table_response: Build consistent table responses in markdown
  - build_info_response: Build info display responses in markdown
"""

import ast
import json
import sys
from io import StringIO
from typing import Any, List, Tuple, Dict
from replkit2.textkit import markdown
from webtap.commands._symbols import sym


def evaluate_expression(expr: str, namespace: dict) -> Tuple[Any, str]:
    """Execute Python code and capture both stdout and the last expression result.

    This mimics Jupyter's execution model where all statements are executed
    and the last expression's value is returned along with captured stdout.

    Args:
        expr: Python code to execute.
        namespace: Dict of variables available to the code.

    Returns:
        Tuple of (result, stdout_output).
    """
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    result = None

    try:
        # Parse the code to find if last node is an expression
        tree = ast.parse(expr)
        if tree.body:
            # If last node is an Expression, evaluate it separately
            if isinstance(tree.body[-1], ast.Expr):
                # Execute all but the last node
                if len(tree.body) > 1:
                    exec_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
                    exec(compile(exec_tree, "<string>", "exec"), namespace)
                # Evaluate the last expression
                result = eval(compile(ast.Expression(body=tree.body[-1].value), "<string>", "eval"), namespace)
            else:
                # All statements, just exec everything
                exec(compile(tree, "<string>", "exec"), namespace)

    except SyntaxError:
        # Fallback to simple exec if parsing fails
        exec(expr, namespace)
    finally:
        # Always restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()

    return result, output


def format_expression_result(result: Any, output: str, max_length: int = 2000) -> str:
    """Format the result of an expression evaluation for display.

    Args:
        result: The evaluation result.
        output: Any stdout output captured.
        max_length: Maximum length before truncation. Defaults to 2000.

    Returns:
        Formatted string combining output and result.
    """
    parts = []

    if output:
        parts.append(output.rstrip())

    if result is not None:
        if isinstance(result, (dict, list)):
            formatted = json.dumps(result, indent=2)
            if len(formatted) > max_length:
                parts.append(formatted[:max_length] + f"\n... [truncated, {len(formatted)} chars total]")
            else:
                parts.append(formatted)
        elif isinstance(result, str) and len(result) > max_length:
            parts.append(result[:max_length] + f"\n... [truncated, {len(result)} chars total]")
        else:
            parts.append(str(result))

    return "\n".join(parts) if parts else "(no output)"


def truncate_string(text: str, max_length: int, mode: str = "end") -> str:
    """Truncate string with ellipsis for table display.

    Replaces newlines and tabs with spaces, then truncates if needed.

    Args:
        text: String to truncate.
        max_length: Maximum length including ellipsis.
        mode: Truncation mode - "end", "middle", or "start". Defaults to "end".

    Returns:
        Truncated string with ellipsis if needed.
    """
    if not text:
        return sym("empty")

    # Replace newlines and tabs with spaces for table display
    text = text.replace("\n", " ").replace("\t", " ")

    if len(text) <= max_length:
        return text

    if max_length < 5:  # Too short for meaningful truncation
        return text[:max_length]

    if mode == "middle":
        # Keep start and end (useful for URLs, file paths)
        keep_start = (max_length - 3) // 2
        keep_end = max_length - 3 - keep_start
        return f"{text[:keep_start]}...{text[-keep_end:]}" if keep_end > 0 else f"{text[:keep_start]}..."
    elif mode == "start":
        # Keep end (useful for file names)
        return f"...{text[-(max_length - 3) :]}"
    else:  # mode == "end" (default)
        # Keep start (useful for most text)
        return f"{text[: max_length - 3]}..."


def format_size(size_bytes: str | int | None) -> str:
    """Format byte size as human-readable string.

    Args:
        size_bytes: Size in bytes (string or int).

    Returns:
        Formatted size string (e.g., "1.2K", "3.4M", "5.6G").
    """
    if not size_bytes:
        return sym("empty")

    try:
        # Convert to int if string
        if isinstance(size_bytes, str):
            if not size_bytes.isdigit():
                return sym("empty")
            size_bytes = int(size_bytes)

        # Format based on size
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}K"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}M"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}G"
    except (ValueError, TypeError):
        return sym("empty")


def format_id(id_string: str | None, length: int | None = None) -> str:
    """Format ID string with optional truncation.

    Args:
        id_string: ID to format.
        length: Optional target length (no truncation if None).

    Returns:
        Formatted ID (no truncation by default).
    """
    if not id_string:
        return sym("empty")

    # No truncation by default - show full ID
    if length is None:
        return id_string

    if len(id_string) <= length:
        return id_string

    # If length specified and ID is longer, truncate
    return f"{id_string[:length]}..."


def process_events_query_results(
    results: List[Tuple], discovered_fields: Dict[str, List[str]], max_width: int = 80
) -> List[Dict[str, str]]:
    """Process CDP event query results into table rows.

    Takes query results where first column is rowid, followed by extracted field values,
    and returns table rows with ID, Field, and Value columns for display.

    Args:
        results: Query results - list of tuples (rowid, field1_value, field2_value, ...).
        discovered_fields: Field mappings from build_query {"url": ["params.response.url", ...], ...}.
        max_width: Maximum width for value truncation. Defaults to 80.

    Returns:
        List of dicts with ID, Field, Value keys for table display.
    """
    rows = []

    for result_row in results:
        # First column is always rowid
        rowid = result_row[0]
        col_index = 1

        # Process each discovered field
        for field_name, field_paths in discovered_fields.items():
            for field_path in field_paths:
                if col_index < len(result_row):
                    value = result_row[col_index]
                    if value is not None:
                        rows.append(
                            {
                                "ID": str(rowid),
                                "Field": field_path,
                                "Value": truncate_string(str(value), max_width),
                            }
                        )
                    col_index += 1

    return rows


def build_table_response(
    title: str, headers: list[str], rows: list[dict], summary: str | None = None, warnings: list[str] | None = None
) -> dict:
    """Build consistent table response in markdown format.

    Args:
        title: Table title.
        headers: Column headers.
        rows: Data rows as dicts.
        summary: Optional summary text.
        warnings: Optional warning messages.

    Returns:
        Markdown dict with formatted table.
    """
    builder = markdown().heading(title, level=2)

    if warnings:
        for warning in warnings:
            builder.element("alert", message=warning, level="warning")

    if rows:
        builder.element("table", headers=headers, rows=rows)
    else:
        builder.text("_No data available_")

    if summary:
        builder.text(f"_{summary}_")

    return builder.build()


def build_info_response(title: str, fields: dict, extra: str | None = None) -> dict:
    """Build info display response in markdown format.

    Args:
        title: Info display title.
        fields: Dict of field names to values.
        extra: Optional extra content to append.

    Returns:
        Markdown dict with formatted info display.
    """
    builder = markdown().heading(title, level=2)

    for key, value in fields.items():
        if value is not None:
            builder.text(f"**{key}:** {value}")

    if extra:
        builder.raw(extra)

    return builder.build()
