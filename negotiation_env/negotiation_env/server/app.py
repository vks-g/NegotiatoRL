"""
FastAPI application for the Negotiation Environment server.

This module creates the FastAPI app using OpenEnv's create_app utility,
which automatically generates all required endpoints:
- /ws - WebSocket endpoint for real-time communication
- /reset - HTTP endpoint to start a new episode
- /step - HTTP endpoint to take an action
- /state - HTTP endpoint to get current state
- /health - Health check endpoint
- /docs - OpenAPI documentation

Note: We pass the class (not instance) to create_app. This allows:
- HTTP endpoints: Uses a singleton/shared environment instance
- WebSocket: Creates a new instance per connection for session isolation
"""

from openenv.core.env_server import create_app

from .environment import NegotiationEnvironment
from ..models import NegotiationAction, NegotiationObservation

# Create the FastAPI application
# Passing the class enables both HTTP (singleton) and WebSocket (per-session) modes
app = create_app(
    NegotiationEnvironment,
    NegotiationAction,
    NegotiationObservation,
)
