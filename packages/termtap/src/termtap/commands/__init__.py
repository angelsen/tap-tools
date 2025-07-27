"""Termtap commands - minimal set."""

# Import to trigger @app.command decorators
from . import execution  # noqa: F401
from . import inspection  # noqa: F401
from . import utils  # noqa: F401

# Export for convenience
from .execution import bash, interrupt
from .inspection import read, ls
from .utils import reload

__all__ = ["bash", "interrupt", "read", "ls", "reload"]