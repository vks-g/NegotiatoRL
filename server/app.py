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

# Import the app factory. Prefer 'create_app': it serves the Gradio web UI at
# /web when ENABLE_WEB_INTERFACE=true (set in the Dockerfile, and the Space's
# README sets base_path: /web). 'create_fastapi_app' is the API-only factory, so
# using it made the Space page show {"detail":"Not Found"}. Fall back to it
# only for older openenv-core releases that lack 'create_app'.
try:
    from openenv.core.env_server import create_app as _create_app
except ImportError:
    try:
        from openenv.core.env_server import create_fastapi_app as _create_app  # type: ignore[no-redef]
    except ImportError as e:
        raise ImportError(
            "Could not import app factory from openenv.core.env_server. "
            "Tried: create_app, create_fastapi_app. "
            f"Original error: {e}"
        ) from e

from .environment import NegotiationEnvironment
from models import NegotiationAction, NegotiationObservation

# Create the FastAPI application.
# Passing the class (not an instance) allows the framework to manage
# lifecycle: singleton for HTTP, per-connection instance for WebSocket.
try:
    from .negotiate_ui import build_negotiate_tab

    # A "Negotiate" tab with one slider per issue, shown first. The auto-generated
    # Playground stays as the second tab.
    app = _create_app(
        NegotiationEnvironment,
        NegotiationAction,
        NegotiationObservation,
        gradio_builder=build_negotiate_tab,
        custom_tab_name="Negotiate",
        custom_tab_primary=True,
    )
except (ImportError, TypeError):
    # Older openenv-core (no gradio_builder) or the API-only factory.
    app = _create_app(
        NegotiationEnvironment,
        NegotiationAction,
        NegotiationObservation,
    )


def main() -> None:
    """
    Main entry point for running the server directly.
    This function is required by openenv validate for multi-mode deployment.
    """
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
