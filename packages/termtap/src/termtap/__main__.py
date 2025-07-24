"""termtap CLI entry point."""

import sys
from .app import app


def main():
    """Main entry point."""
    if "--mcp" in sys.argv:
        # Run as MCP server
        app.mcp.run()
    else:
        # Run as REPL
        app.run(title="termtap - Terminal Session Manager")


if __name__ == "__main__":
    main()
