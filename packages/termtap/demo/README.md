# Termtap Demo

This demo showcases termtap's ready pattern detection with a FastAPI backend and SvelteKit frontend.

## Configuration

The `termtap.toml` file configures ready patterns for each service:
- **backend**: Detects "Uvicorn running on" 
- **frontend**: Detects "Local:\s+https?://localhost:\d+"

## Running the Demo

From the demo directory, use termtap to start services:

```python
# Start backend (FastAPI on port 8000)
bash("python -m backend", "backend")
# Returns immediately when "Uvicorn running on" is detected

# Start frontend (SvelteKit on port 5173)  
bash("npm run dev", "frontend")
# Returns immediately when "Local: http://localhost:5173" is detected
```

Both commands will return with status="ready" as soon as the services are ready to accept requests, instead of timing out.

## Backend

The backend is a simple FastAPI application with:
- `/` - Hello message
- `/health` - Health check endpoint

Run directly: `python -m backend`

## Frontend

The frontend is a SvelteKit application (setup required).

Run directly: `npm run dev`