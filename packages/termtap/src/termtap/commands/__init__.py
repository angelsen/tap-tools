"""Termtap commands - one command per file."""

# Import to trigger @app.command decorators
from . import bash as _bash  # noqa: F401
from . import interrupt as _interrupt  # noqa: F401
from . import read as _read  # noqa: F401
from . import ls as _ls  # noqa: F401
from . import reload as _reload  # noqa: F401
from . import init as _init  # noqa: F401
from . import track as _track  # noqa: F401

# Export for convenience (imported from their own modules)
from .bash import bash
from .interrupt import interrupt
from .read import read
from .ls import ls
from .reload import reload
from .init import init, init_list, kill
from .track import track

__all__ = ["bash", "interrupt", "read", "ls", "reload", "init", "init_list", "kill", "track"]
