"""Utility functions for command formatting."""

from typing import List, Tuple, Dict


def truncate_string(text: str, max_length: int, mode: str = "end") -> str:
    """
    Truncate string with ellipsis.
    
    Args:
        text: String to truncate
        max_length: Maximum length including ellipsis
        mode: "end", "middle", or "start"
        
    Returns:
        Truncated string with ellipsis if needed
    """
    if not text:
        return "-"
    
    # Replace newlines and tabs with spaces for table display
    text = text.replace('\n', ' ').replace('\t', ' ')
    
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
        return f"...{text[-(max_length-3):]}"
    else:  # mode == "end" (default)
        # Keep start (useful for most text)
        return f"{text[:max_length-3]}..."


def format_size(size_bytes: str | int | None) -> str:
    """
    Format byte size as human-readable string.
    
    Args:
        size_bytes: Size in bytes (string or int)
        
    Returns:
        Formatted size string (e.g., "1.2K", "3.4M", "5.6G")
    """
    if not size_bytes:
        return "-"
    
    try:
        # Convert to int if string
        if isinstance(size_bytes, str):
            if not size_bytes.isdigit():
                return "-"
            size_bytes = int(size_bytes)
        
        # Format based on size
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}K"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f}M"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f}G"
    except (ValueError, TypeError):
        return "-"


def format_id(id_string: str | None, length: int | None = None) -> str:
    """
    Format ID string.
    
    Args:
        id_string: ID to format
        length: Optional target length (no truncation if None)
        
    Returns:
        Formatted ID (no truncation by default)
    """
    if not id_string:
        return "-"
    
    # No truncation by default - show full ID
    if length is None:
        return id_string
    
    if len(id_string) <= length:
        return id_string
    
    # If length specified and ID is longer, truncate
    return f"{id_string[:length]}..."


def process_query_results_for_table(results: List[Tuple], discovered: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """
    Process query results into field-value pairs for table display.
    
    Takes the raw query results and discovered field mappings,
    and returns a flat list of (field_path, value) tuples suitable
    for caching and table display.
    
    Args:
        results: Query results - list of tuples with extracted values
        discovered: Discovered fields mapping from build_query
        
    Returns:
        List of (field_path, value) tuples with non-null values
    """
    field_value_pairs = []
    
    for row in results:
        col_idx = 0
        
        # Iterate through discovered fields in order
        for key, paths in discovered.items():
            for path in paths:
                if col_idx < len(row):
                    value = row[col_idx]
                    if value:  # Only include non-null values
                        field_value_pairs.append((path, value))
                col_idx += 1
    
    return field_value_pairs