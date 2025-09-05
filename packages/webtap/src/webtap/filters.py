"""Network request filter management for WebTap.

PUBLIC API:
  - FilterManager: Main filter management class
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class FilterManager:
    """Manages network request filters for noise reduction.

    Provides filtering of CDP network events based on domain patterns and resource
    types. Filters are organized into categories that can be enabled/disabled
    independently. Supports wildcard patterns and generates SQL WHERE clauses
    for efficient event filtering.

    Attributes:
        filter_path: Path to the filters.json file.
        filters: Dict mapping category names to filter patterns.
        enabled_categories: Set of currently enabled filter categories.
    """

    def __init__(self, filter_path: Path | None = None):
        """Initialize filter manager.

        Args:
            filter_path: Path to filters.json file. Defaults to .webtap/filters.json.
        """
        self.filter_path = filter_path or (Path.cwd() / ".webtap" / "filters.json")
        self.filters: Dict[str, Dict[str, List[str]]] = {}
        self.enabled_categories: set[str] = set()

    def load(self) -> bool:
        """Load filters from disk.

        Loads filter configuration from the JSON file and enables all categories
        by default. Creates empty filter dict if file doesn't exist or fails to load.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if self.filter_path.exists():
            try:
                with open(self.filter_path) as f:
                    self.filters = json.load(f)
                    # Enable all categories by default
                    self.enabled_categories = set(self.filters.keys())
                    logger.info(f"Loaded {len(self.filters)} filter categories from {self.filter_path}")
                    return True
            except Exception as e:
                logger.error(f"Failed to load filters: {e}")
                self.filters = {}
                return False
        else:
            logger.info(f"No filters found at {self.filter_path}")
            self.filters = {}
            return False

    def save(self) -> bool:
        """Save current filters to disk.

        Creates the parent directory if it doesn't exist and writes the filter
        configuration as JSON with indentation.

        Returns:
            True if saved successfully, False on error.
        """
        try:
            self.filter_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filter_path, "w") as f:
                json.dump(self.filters, f, indent=2)
            logger.info(f"Saved filters to {self.filter_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save filters: {e}")
            return False

    def add_pattern(self, pattern: str, category: str, pattern_type: str = "domain") -> bool:
        """Add a filter pattern to a category.

        Creates the category if it doesn't exist and enables it. Supports wildcard
        patterns using * for matching. Patterns are deduplicated within categories.

        Args:
            pattern: Pattern to add (e.g., "*ads*", "googletagmanager.com").
            category: Category name (e.g., "ads", "tracking").
            pattern_type: "domain" or "type". Defaults to "domain".

        Returns:
            True if pattern was added, False if it already existed.
        """
        if category not in self.filters:
            self.filters[category] = {"domains": [], "types": []}
            self.enabled_categories.add(category)

        key = "domains" if pattern_type == "domain" else "types"
        if pattern not in self.filters[category][key]:
            self.filters[category][key].append(pattern)
            return True
        return False

    def remove_pattern(self, pattern: str, pattern_type: str = "domain") -> str:
        """Remove a pattern from all categories.

        Searches through all categories to find and remove the specified pattern.
        Only removes the first occurrence found.

        Args:
            pattern: Pattern to remove.
            pattern_type: "domain" or "type". Defaults to "domain".

        Returns:
            Category name it was removed from, or empty string if not found.
        """
        key = "domains" if pattern_type == "domain" else "types"
        for category, filters in self.filters.items():
            if pattern in filters.get(key, []):
                filters[key].remove(pattern)
                return category
        return ""

    def update_category(self, category: str, domains: List[str] | None = None, types: List[str] | None = None):
        """Update or create a category with new patterns.

        Creates the category if it doesn't exist and enables it. If patterns are
        provided, they completely replace the existing patterns for that type.

        Args:
            category: Category name.
            domains: List of domain patterns. None leaves existing unchanged.
            types: List of type patterns. None leaves existing unchanged.
        """
        if category not in self.filters:
            self.filters[category] = {"domains": [], "types": []}

        if domains is not None:
            self.filters[category]["domains"] = domains
        if types is not None:
            self.filters[category]["types"] = types

        self.enabled_categories.add(category)

    def delete_category(self, category: str) -> bool:
        """Delete a filter category.

        Removes the category and all its patterns. Also removes it from the
        enabled categories set.

        Args:
            category: Category name to delete.

        Returns:
            True if category was deleted, False if it didn't exist.
        """
        if category in self.filters:
            del self.filters[category]
            self.enabled_categories.discard(category)
            return True
        return False

    def set_enabled_categories(self, categories: List[str] | None = None):
        """Set which categories are enabled for filtering.

        Only enabled categories are used when generating SQL filter clauses.
        Invalid category names are silently ignored.

        Args:
            categories: List of category names to enable. None enables all categories.
        """
        if categories is None:
            self.enabled_categories = set(self.filters.keys())
        else:
            self.enabled_categories = set(categories) & set(self.filters.keys())

    def get_filter_sql(self, use_all: bool = True, categories: List[str] | None = None) -> str:
        """Generate SQL WHERE clause for filtering CDP events.

        Creates SQL conditions to exclude network requests matching the filter
        patterns. Handles wildcard patterns by converting them to SQL LIKE patterns
        and properly escapes SQL strings.

        Args:
            use_all: Use all enabled categories. Defaults to True.
            categories: Specific categories to use (overrides use_all).

        Returns:
            SQL WHERE clause string, or empty string if no filters apply.
        """
        if not self.filters:
            return ""

        # Determine which categories to use
        if categories:
            active_categories = set(categories) & set(self.filters.keys())
        elif use_all:
            active_categories = self.enabled_categories
        else:
            return ""

        if not active_categories:
            return ""

        # Collect all patterns
        all_domains = []
        all_types = []

        for category in active_categories:
            all_domains.extend(self.filters[category].get("domains", []))
            all_types.extend(self.filters[category].get("types", []))

        # Build filter conditions - exclude matching items
        exclude_conditions = []

        # Domain filtering - exclude URLs matching these patterns
        if all_domains:
            for pattern in all_domains:
                # Convert wildcard to SQL LIKE pattern, escape single quotes for SQL safety
                sql_pattern = pattern.replace("'", "''").replace("*", "%")
                # For Network.responseReceived events - filter on what's actually there
                exclude_conditions.append(
                    f"json_extract_string(event, '$.params.response.url') NOT LIKE '{sql_pattern}'"
                )

        # Type filtering - exclude these types
        if all_types:
            # Escape single quotes in types for SQL safety
            escaped_types = [t.replace("'", "''") for t in all_types]
            type_list = ", ".join(f"'{t}'" for t in escaped_types)
            # Use COALESCE to handle NULL types properly, exclude matching types
            exclude_conditions.append(
                f"(COALESCE(json_extract_string(event, '$.params.type'), '') NOT IN ({type_list}) OR "
                f"json_extract_string(event, '$.params.type') IS NULL)"
            )

        if exclude_conditions:
            # Use AND to ensure ALL conditions are met (item doesn't match ANY filter)
            return f"({' AND '.join(exclude_conditions)})"

        return ""

    def get_status(self) -> Dict[str, Any]:
        """Get current filter status and statistics.

        Provides comprehensive information about loaded filters including
        category counts, enabled status, and file path.

        Returns:
            Dict with filter information including loaded status, categories,
            enabled categories, pattern counts, and file path.
        """
        return {
            "loaded": bool(self.filters),
            "categories": list(self.filters.keys()),
            "enabled": list(self.enabled_categories),
            "total_domains": sum(len(f.get("domains", [])) for f in self.filters.values()),
            "total_types": sum(len(f.get("types", [])) for f in self.filters.values()),
            "path": str(self.filter_path),
        }

    def get_display_info(self) -> str:
        """Get formatted filter information for display.

        Creates a human-readable summary of all filter categories with their
        enabled status and pattern counts.

        Returns:
            Formatted multiline string with filter details.
        """
        if not self.filters:
            return f"No filters loaded (would load from {self.filter_path})"

        lines = [f"Loaded filters from {self.filter_path}:"]
        for category in sorted(self.filters.keys()):
            filters = self.filters[category]
            enabled = "✓" if category in self.enabled_categories else "✗"
            domains = len(filters.get("domains", []))
            types = len(filters.get("types", []))
            lines.append(f"  {enabled} {category}: {domains} domains, {types} types")

        return "\n".join(lines)


__all__ = ["FilterManager"]
