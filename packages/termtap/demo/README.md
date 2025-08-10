# Termtap Demo

This demo showcases termtap's service orchestration with ready pattern detection using a FastAPI backend and SvelteKit frontend.

## Configuration

The `termtap.toml` file defines the service group with ready patterns:
- **backend**: Detects "Uvicorn running on" to know when FastAPI is ready
- **frontend**: Detects "Local:.*localhost" to know when Vite dev server is ready

## Running the Demo

Use termtap's `run` command to orchestrate all services:

```python
# Start all services with dependency management
run("demo")

# This will:
# 1. Create a tmux session named "demo"
# 2. Start backend in pane 0
# 3. Wait for backend to be ready (Uvicorn pattern match)
# 4. Start frontend in pane 1 (depends on backend)
# 5. Wait for frontend to be ready (Vite pattern match)
# 6. Return with status showing all services running
```

## Working with Services

Once running, you can interact with services using their names:

```python
# Read output from specific services
read("demo.backend")   # Read backend logs
read("demo.frontend")  # Read frontend logs

# Send commands to services
execute("curl http://localhost:8000/health", "demo.backend")
send_keys("demo.frontend", "r")  # Send 'r' to trigger Vite refresh

# Interrupt a service
interrupt("demo.backend")  # Send Ctrl+C to backend

# Stop all services
kill("demo")  # Terminates the entire session
```

## Pane-Centric Access

You can also work directly with panes:

```python
from termtap.pane import Pane, send_command

# Get pane for backend service
pane = Pane("%0")  # Or use resolve_target("demo.backend")

# Check pane state
print(pane.process)          # Shows "uvicorn" or "node"
print(pane.visible_content)  # Current terminal content

# Send commands with full control
result = send_command(
    pane, 
    "curl http://localhost:8000/",
    ready_pattern="Hello.*World"
)
print(result["status"])  # "ready" when pattern matches
print(result["elapsed"])  # Time taken
```

## Service Details

### Backend (FastAPI)
- **Port**: 8000
- **Endpoints**: 
  - `/` - Hello message
  - `/health` - Health check
- **Ready Pattern**: "Uvicorn running on"
- **Run directly**: `python -m backend`

### Frontend (SvelteKit)  
- **Port**: 5173
- **Dev Server**: Vite with HMR
- **Ready Pattern**: "Local:.*localhost"
- **Run directly**: `npm run dev`

## Configuration File

The `termtap.toml` shows best practices:
- Service dependencies (frontend depends on backend)
- Ready patterns for reliable startup detection
- Path configuration for correct working directories
- Timeout settings for slow-starting services