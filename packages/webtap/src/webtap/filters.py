"""Network request filter management for WebTap.

Provides filtering of CDP network events to reduce noise from ads, tracking, etc.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class FilterManager:
    """Manages network request filters for noise reduction."""

    def __init__(self, filter_path: Path | None = None):
        """Initialize filter manager.

        Args:
            filter_path: Path to filters.json file, defaults to .webtap/filters.json
        """
        self.filter_path = filter_path or (Path.cwd() / ".webtap" / "filters.json")
        self.filters: Dict[str, Dict[str, List[str]]] = {}
        self.enabled_categories: set[str] = set()

    def load(self) -> bool:
        """Load filters from disk.

        Returns:
            True if loaded successfully, False otherwise
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

        Returns:
            True if saved successfully
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
        """Add a filter pattern.

        Args:
            pattern: Pattern to add (e.g., "*ads*")
            category: Category name (e.g., "ads")
            pattern_type: "domain" or "type"

        Returns:
            True if added successfully
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

        Args:
            pattern: Pattern to remove
            pattern_type: "domain" or "type"

        Returns:
            Category it was removed from, or empty string
        """
        key = "domains" if pattern_type == "domain" else "types"
        for category, filters in self.filters.items():
            if pattern in filters.get(key, []):
                filters[key].remove(pattern)
                return category
        return ""

    def update_category(self, category: str, domains: List[str] | None = None, types: List[str] | None = None):
        """Update or create a category.

        Args:
            category: Category name
            domains: List of domain patterns
            types: List of type patterns
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

        Args:
            category: Category to delete

        Returns:
            True if deleted
        """
        if category in self.filters:
            del self.filters[category]
            self.enabled_categories.discard(category)
            return True
        return False

    def set_enabled_categories(self, categories: List[str] | None = None):
        """Set which categories are enabled.

        Args:
            categories: List of category names to enable, None for all
        """
        if categories is None:
            self.enabled_categories = set(self.filters.keys())
        else:
            self.enabled_categories = set(categories) & set(self.filters.keys())

    def get_filter_sql(self, use_all: bool = True, categories: List[str] | None = None) -> str:
        """Generate SQL WHERE clause for filtering.

        Args:
            use_all: Use all enabled categories
            categories: Specific categories to use (overrides use_all)

        Returns:
            SQL WHERE clause string, or empty string if no filters
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

        # Build filter conditions - we'll exclude matching items
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
        """Get current filter status.

        Returns:
            Dict with filter information
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

        Returns:
            Formatted string with filter details
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
