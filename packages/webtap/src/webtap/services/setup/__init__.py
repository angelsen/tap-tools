"""Setup service for installing WebTap components.

PUBLIC API:
  - SetupService: Main service class for all setup operations
"""

from typing import Dict, Any

from .filters import install_filters
from .extension import install_extension
from .chrome import install_chrome_wrapper
from .desktop import install_desktop_entry


class SetupService:
    """Service for installing WebTap components.

    Delegates to specialized modules for each component type.
    """

    def install_filters(self, force: bool = False) -> Dict[str, Any]:
        """Install filter configuration.

        Args:
            force: Overwrite existing file

        Returns:
            Dict with success, message, path, details
        """
        return install_filters(force=force)

    def install_extension(self, force: bool = False) -> Dict[str, Any]:
        """Install Chrome extension files.

        Args:
            force: Overwrite existing files

        Returns:
            Dict with success, message, path, details
        """
        return install_extension(force=force)

    def install_chrome_wrapper(self, force: bool = False) -> Dict[str, Any]:
        """Install Chrome wrapper script.

        Args:
            force: Overwrite existing script

        Returns:
            Dict with success, message, path, details
        """
        return install_chrome_wrapper(force=force)

    def install_desktop_entry(self, force: bool = False) -> Dict[str, Any]:
        """Install desktop entry for GUI integration.

        Args:
            force: Overwrite existing entry

        Returns:
            Dict with success, message, path, details
        """
        return install_desktop_entry(force=force)


__all__ = ["SetupService"]
