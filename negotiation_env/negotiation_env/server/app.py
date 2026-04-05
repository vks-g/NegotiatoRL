"""
FastAPI application for the Negotiation Environment server.

This module creates the FastAPI app using OpenEnv's app factory,
which automatically generates all required endpoints:
- /ws   - WebSocket endpoint for real-time communication
- /reset - HTTP endpoint to start a new episode
- /step  - HTTP endpoint to take an action
- /state - HTTP endpoint to get current state
- /health - Health check endpoint
- /docs  - OpenAPI documentation

Note: We pass the class (not instance) to the factory. This allows:
- HTTP endpoints: Uses a singleton/shared environment instance
- WebSocket: Creates a new instance per connection for session isolation
"""

# Import the app factory — try the documented name first, fall back to alias.
# openenv-core may export either 'create_fastapi_app' (spec name) or 'create_app' (alias).
try:
    from openenv.core.env_server import create_fastapi_app as _create_app
except ImportError:
    try:
        from openenv.core.env_server import create_app as _create_app  # type: ignore[no-redef]
    except ImportError as e:
        raise ImportError(
            "Could not import app factory from openenv.core.env_server. "
            "Tried: create_fastapi_app, create_app. "
            f"Original error: {e}"
        ) from e

from .environment import NegotiationEnvironment
from ..models import NegotiationAction, NegotiationObservation

# Create the FastAPI application.
# Passing the class (not an instance) allows the framework to manage
# lifecycle: singleton for HTTP, per-connection instance for WebSocket.
app = _create_app(
    NegotiationEnvironment,
    NegotiationAction,
    NegotiationObservation,
)
