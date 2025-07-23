# tap-tools

A suite of tools for tapping into terminals, web pages, and logs for LLM-assisted debugging and automation.

## Tools

- **termtap** - Tap into terminal sessions with smart detection for TUIs, REPLs, and debuggers
- **webtap** - Tap into web pages and mark elements for LLM understanding and automation
- **logtap** - Tap into log streams from multiple sources with unified event correlation

## Architecture

This is a UV workspace monorepo where each tool:
- Can be developed and versioned independently
- Shares common dependencies through the workspace
- Can be installed separately or as a suite
- Exposes functionality via MCP (Model Context Protocol) servers

## Development

```bash
# Install all tools for development
uv sync

# Run individual tools
uv run --package termtap serve
uv run --package webtap serve
uv run --package logtap serve
```

## Author

Fredrik Angelsen