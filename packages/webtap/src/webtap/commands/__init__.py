"""WebTap commands - import all to register with app."""

# Import all command modules to register them
from webtap.commands import connection, navigation, execution, network, console

__all__ = ["connection", "navigation", "execution", "network", "console"]
