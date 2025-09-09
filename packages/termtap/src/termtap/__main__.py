"""Process-native tmux pane manager with MCP support.

Entry point for termtap application when run as a module (python -m termtap).
"""

import logging

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_LOG_DATEFMT = "%H:%M:%S"

logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, datefmt=_LOG_DATEFMT)

if __name__ == "__main__":
    from . import main
    main()
