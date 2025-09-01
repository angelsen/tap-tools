# Chrome DevTools Protocol Schema

This directory contains the CDP protocol schema and version information fetched from Chrome.

## Files

- `cdp_protocol.json` - Full CDP protocol schema with all domains, commands, events, and types
- `cdp_version.json` - Chrome version and protocol version information

## Fetching Latest Schema

To update these files with the latest protocol from your Chrome instance:

```bash
# Ensure Chrome is running with debugging enabled:
# google-chrome --remote-debugging-port=9222

# Fetch protocol schema
curl -s http://localhost:9222/json/protocol > cdp_protocol.json

# Fetch version info
curl -s http://localhost:9222/json/version | jq '.' > cdp_version.json
```

## Using the Schema

These files are useful for:
- Understanding available CDP commands and their parameters
- Debugging protocol issues
- Validating command usage
- Discovering new CDP features

## Example: Finding Fetch Commands

```bash
# List all Fetch domain commands
cat cdp_protocol.json | jq '.domains[] | select(.domain == "Fetch") | .commands[].name'

# Get details for a specific command
cat cdp_protocol.json | jq '.domains[] | select(.domain == "Fetch") | .commands[] | select(.name == "continueResponse")'
```