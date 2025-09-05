"""SDP experimental server for Svelte debugging."""

import json
import logging
from typing import List

import duckdb
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)

# Create FastAPI app with CORS for browser access
app = FastAPI(title="SDP Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory DuckDB for event storage
db = duckdb.connect(":memory:")
db.execute("CREATE TABLE IF NOT EXISTS events (event JSON)")

# Track active connections for monitoring
connections: List[WebSocket] = []


@app.websocket("/sdp")
async def sdp_endpoint(websocket: WebSocket):
    """Handle SDP events from Svelte applications."""
    await websocket.accept()
    connections.append(websocket)
    print(f"[SDP] Client connected ({len(connections)} active)")

    try:
        while True:
            # Receive and store event as-is
            data = await websocket.receive_text()
            event = json.loads(data)

            # Store in DuckDB
            db.execute("INSERT INTO events VALUES (?)", [data])

            # Log summary
            method = event.get("method", "unknown")
            params = event.get("params", {})
            print(f"[SDP] {method}: {params.get('statePath', params.get('componentType', ''))}")

    except WebSocketDisconnect:
        connections.remove(websocket)
        print(f"[SDP] Client disconnected ({len(connections)} active)")
    except Exception as e:
        logger.error(f"Error: {e}")
        if websocket in connections:
            connections.remove(websocket)


@app.get("/")
async def status():
    """Check server status and event count."""
    result = db.execute("SELECT COUNT(*) FROM events").fetchone()
    count = result[0] if result else 0
    return {"status": "running", "events": count, "connections": len(connections)}


# Simple query helpers for REPL usage
def query(sql: str):
    """Execute SQL query on events."""
    return db.execute(sql).fetchall()


def events(n: int = 10):
    """Get last n events."""
    return db.execute(f"SELECT event FROM events ORDER BY rowid DESC LIMIT {n}").fetchall()


def clear():
    """Clear all events."""
    db.execute("DELETE FROM events")
    print("[SDP] Events cleared")


def count():
    """Get total event count."""
    result = db.execute("SELECT COUNT(*) FROM events").fetchone()
    return result[0] if result else 0


def run_server(port: int = 8766):
    """Run the SDP server."""
    print(f"[SDP] Starting server on http://localhost:{port}")
    print(f"[SDP] WebSocket endpoint: ws://localhost:{port}/sdp")
    uvicorn.run(app, host="localhost", port=port, log_level="error")


if __name__ == "__main__":
    run_server()
