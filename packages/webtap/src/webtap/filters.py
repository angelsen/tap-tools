"""Network request filter management for WebTap."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FilterGroup:
    """A named filter group with hide configuration."""

    hide: dict  # {"types": [...], "urls": [...]}


class FilterManager:
    """Manages filter groups with file persistence and memory toggle state.

    Groups define what to hide (types, URL patterns). Enabled state is in-memory
    only - all groups start disabled on load. Group definitions persist to file.
    """

    def __init__(self, filter_path: Path | str | None = None):
        """Initialize filter manager.

        Args:
            filter_path: Path to filters.json. Defaults to .webtap/filters.json.
        """
        if filter_path is None:
            self.filter_path = Path.cwd() / ".webtap" / "filters.json"
        else:
            self.filter_path = Path(filter_path)
        self.groups: dict[str, FilterGroup] = {}
        self.enabled: set[str] = set()

    def load(self) -> bool:
        """Load group definitions from file. All disabled by default.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if self.filter_path.exists():
            try:
                with open(self.filter_path) as f:
                    data = json.load(f)
                self.groups = {
                    name: FilterGroup(hide=cfg.get("hide", {"types": [], "urls": []}))
                    for name, cfg in data.get("groups", {}).items()
                }
                self.enabled = set()  # All disabled on load
                logger.info(f"Loaded {len(self.groups)} filter groups from {self.filter_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to load filters: {e}")
                self.groups = {}
                return False
        else:
            logger.debug(f"No filters found at {self.filter_path}")
            self.groups = {}
            return False

    def save(self) -> bool:
        """Save group definitions to file (not enabled state).

        Returns:
            True if saved successfully, False on error.
        """
        try:
            self.filter_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"groups": {name: {"hide": group.hide} for name, group in self.groups.items()}}
            with open(self.filter_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved filters to {self.filter_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save filters: {e}")
            return False

    def add(self, name: str, hide: dict) -> None:
        """Add a group definition and persist to file.

        Args:
            name: Group name.
            hide: Filter config {"types": [...], "urls": [...]}.
        """
        # Ensure hide has required keys
        normalized_hide = {
            "types": hide.get("types", []),
            "urls": hide.get("urls", []),
        }
        self.groups[name] = FilterGroup(hide=normalized_hide)
        self.save()

    def remove(self, name: str) -> bool:
        """Remove a group and persist to file.

        Args:
            name: Group name to remove.

        Returns:
            True if removed, False if not found.
        """
        if name in self.groups:
            del self.groups[name]
            self.enabled.discard(name)
            self.save()
            return True
        return False

    def enable(self, name: str) -> bool:
        """Enable a group (in-memory only).

        Args:
            name: Group name to enable.

        Returns:
            True if group exists and was enabled, False otherwise.
        """
        if name in self.groups:
            self.enabled.add(name)
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a group (in-memory only).

        Args:
            name: Group name to disable.

        Returns:
            True if group exists and was disabled, False otherwise.
        """
        if name in self.groups:
            self.enabled.discard(name)
            return True
        return False

    def get_active_filters(self) -> dict:
        """Get consolidated filters from enabled groups (deduplicated).

        Returns:
            Dict with "types" and "urls" lists from all enabled groups.
        """
        hide_types: set[str] = set()
        hide_urls: set[str] = set()
        for name in self.enabled:
            if name in self.groups:
                hide_types.update(self.groups[name].hide.get("types", []))
                hide_urls.update(self.groups[name].hide.get("urls", []))
        return {"types": list(hide_types), "urls": list(hide_urls)}

    def get_status(self) -> dict:
        """Get all groups with enabled status.

        Returns:
            Dict mapping group names to their config and enabled status.
        """
        return {
            name: {
                "enabled": name in self.enabled,
                "hide": group.hide,
            }
            for name, group in self.groups.items()
        }

    def build_filter_sql(
        self,
        status: int | None = None,
        method: str | None = None,
        type_filter: str | None = None,
        url: str | None = None,
        apply_groups: bool = True,
    ) -> str:
        """Build SQL WHERE conditions for har_summary filtering.

        Args:
            status: Filter by HTTP status code.
            method: Filter by HTTP method.
            type_filter: Filter by resource type.
            url: Filter by URL pattern (supports * wildcard).
            apply_groups: Apply enabled filter groups.

        Returns:
            SQL WHERE clause conditions (without WHERE keyword).
        """
        conditions = []

        # Inline filters
        if status is not None:
            conditions.append(f"status = {status}")
        if method:
            conditions.append(f"UPPER(method) = '{method.upper()}'")
        if type_filter:
            conditions.append(f"LOWER(type) = '{type_filter.lower()}'")
        if url:
            sql_pattern = url.replace("'", "''").replace("*", "%")
            conditions.append(f"url LIKE '{sql_pattern}'")

        # Apply enabled filter groups
        if apply_groups:
            active = self.get_active_filters()

            # Hide matching types
            if active["types"]:
                escaped_types = [t.replace("'", "''") for t in active["types"]]
                type_list = ", ".join(f"'{t}'" for t in escaped_types)
                conditions.append(f"type NOT IN ({type_list})")

            # Hide matching URLs
            for pattern in active["urls"]:
                sql_pattern = pattern.replace("'", "''").replace("*", "%")
                conditions.append(f"url NOT LIKE '{sql_pattern}'")

        return " AND ".join(conditions) if conditions else ""


__all__ = ["FilterManager"]
