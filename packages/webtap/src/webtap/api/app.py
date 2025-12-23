"""FastAPI application and shared state."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI app
api = FastAPI(title="WebTap API", version="0.1.0")

# Enable CORS for extension
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Chrome extensions have unique origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global reference to WebTap state (set by server.py on startup)
app_state: Any | None = None
