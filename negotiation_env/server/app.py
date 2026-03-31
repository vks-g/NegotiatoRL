"""
FastAPI application for the Negotiation Environment server.

This module creates the FastAPI app using OpenEnv's create_fastapi_app utility,
which automatically generates all required endpoints:
- /ws - WebSocket endpoint for real-time communication
- /reset - HTTP endpoint to start a new episode
- /step - HTTP endpoint to take an action
- /state - HTTP endpoint to get current state
- /health - Health check endpoint
- /docs - OpenAPI documentation
"""

from openenv.core.env_server import create_fastapi_app

from .environment import NegotiationEnvironment
from ..models import NegotiationAction, NegotiationObservation

# Create the FastAPI application
# This automatically generates all OpenEnv endpoints
app = create_fastapi_app(
    env=NegotiationEnvironment,
    action_cls=NegotiationAction,
    observation_cls=NegotiationObservation,
)
