"""SDP Server - Simple FastAPI WebSocket with DuckDB storage.

PUBLIC API:
  - run_server: Run SDP server directly
  - get_server: Get server instance for REPL
"""

import json
import logging
from typing import List

import duckdb
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="SDP Server")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create DuckDB connection
db = duckdb.connect(":memory:")
db.execute("CREATE TABLE IF NOT EXISTS events (event JSON)")

# Active connections
connections: List[WebSocket] = []


@app.websocket("/sdp")
async def sdp_endpoint(websocket: WebSocket):
    """WebSocket endpoint for SDP events."""
    await websocket.accept()
    connections.append(websocket)
    print(f"[SDP] Client connected ({len(connections)} active)")
    
    try:
        while True:
            # Receive and store event
            data = await websocket.receive_text()
            event = json.loads(data)
            
            # Store in DuckDB as-is
            db.execute("INSERT INTO events VALUES (?)", [data])
            
            # Print summary
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
async def root():
    """Health check."""
    count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {
        "status": "running",
        "events": count,
        "connections": len(connections)
    }


def run_server(port: int = 8766):
    """Run the SDP server directly."""
    print(f"[SDP] Starting server on http://localhost:{port}")
    print(f"[SDP] WebSocket endpoint: ws://localhost:{port}/sdp")
    uvicorn.run(app, host="localhost", port=port, log_level="error")


def get_server():
    """Get server components for REPL usage."""
    return {
        "app": app,
        "db": db,
        "connections": connections,
        "query": lambda sql: db.execute(sql).fetchall(),
        "events": lambda n=10: db.execute(f"SELECT event FROM events ORDER BY rowid DESC LIMIT {n}").fetchall(),
        "clear": lambda: db.execute("DELETE FROM events"),
        "count": lambda: db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
    }


if __name__ == "__main__":
    run_server()