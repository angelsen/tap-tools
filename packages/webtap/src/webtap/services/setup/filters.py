"""Filter setup functionality for WebTap."""

import json
import logging
from pathlib import Path
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)

# GitHub URL for filters
FILTERS_URL = "https://raw.githubusercontent.com/angelsen/tap-tools/main/packages/webtap/data/filters.json"


def install_filters(force: bool = False) -> Dict[str, Any]:
    """Install filters to .webtap/filters.json.

    Args:
        force: Overwrite existing file

    Returns:
        Dict with success, message, path, details
    """
    # Same path that FilterManager uses
    target_path = Path.cwd() / ".webtap" / "filters.json"

    # Check if exists
    if target_path.exists() and not force:
        return {
            "success": False,
            "message": f"Filters already exist at {target_path}",
            "path": str(target_path),
            "details": "Use --force to overwrite",
        }

    # Download from GitHub
    try:
        logger.info(f"Downloading filters from {FILTERS_URL}")
        response = requests.get(FILTERS_URL, timeout=10)
        response.raise_for_status()

        # Validate it's proper JSON
        filters_data = json.loads(response.text)

        # Quick validation - should have dict structure
        if not isinstance(filters_data, dict):
            return {
                "success": False,
                "message": "Invalid filter format - expected JSON object",
                "path": None,
                "details": None,
            }

        # Count categories for user feedback
        category_count = len(filters_data)

        # Create directory and save
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(response.text)

        logger.info(f"Saved {category_count} filter categories to {target_path}")

        return {
            "success": True,
            "message": f"Downloaded {category_count} filter categories",
            "path": str(target_path),
            "details": f"Categories: {', '.join(filters_data.keys())}",
        }

    except requests.RequestException as e:
        logger.error(f"Network error downloading filters: {e}")
        return {"success": False, "message": f"Network error: {e}", "path": None, "details": None}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in filters: {e}")
        return {"success": False, "message": f"Invalid JSON format: {e}", "path": None, "details": None}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "message": f"Failed to download filters: {e}", "path": None, "details": None}
