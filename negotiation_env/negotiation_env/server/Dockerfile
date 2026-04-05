# ============================================================================
# Dockerfile for NegotiationEnv Server
# Meta PyTorch OpenEnv Hackathon Submission
# ============================================================================
# 
# IMPORTANT: Build from repository root (required for Hugging Face Spaces)
#   docker build -t negotiation-env:latest -f negotiation_env/negotiation_env/server/Dockerfile .
#
# The Dockerfile path is: negotiation_env/negotiation_env/server/Dockerfile
# (note the double negotiation_env/ — outer folder contains the Python package)
#
# Run:
#   docker run -d -p 8000:8000 negotiation-env:latest
#
# With environment variables:
#   docker run -d -p 8000:8000 \
#       -e WORKERS=4 \
#       -e MAX_CONCURRENT_ENVS=100 \
#       negotiation-env:latest
#
# Test health:
#   curl http://localhost:8000/health
#
# ============================================================================

# Multi-stage build for minimal image size
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only pyproject.toml for dependency caching
COPY negotiation_env/pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "openenv-core>=0.1.0" \
    "pydantic>=2.0.0" \
    "fastapi>=0.100.0" \
    "uvicorn[standard]>=0.23.0" \
    "websockets>=11.0"

# ============================================================================
# Production image - minimal footprint
# ============================================================================
FROM python:3.11-slim AS production

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN addgroup --gid 1001 --system appuser && \
    adduser --uid 1001 --system --gid 1001 --no-create-home appuser

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy the entire negotiation_env package
COPY --chown=appuser:appuser negotiation_env /app/negotiation_env

# Set environment variables
# IMPORTANT: PYTHONPATH must point to the outer negotiation_env/ folder so that
# Python can find the inner negotiation_env/ package (which has __init__.py).
# Container layout after COPY: /app/negotiation_env/negotiation_env/__init__.py
# So PYTHONPATH=/app/negotiation_env makes `import negotiation_env` resolve correctly.
ENV PYTHONPATH="/app/negotiation_env:$PYTHONPATH" \
    PYTHONUNBUFFERED=1 \
    HOST="0.0.0.0" \
    PORT="8000" \
    WORKERS="1"

# Switch to non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the server with correct module path
# Note: Using single worker for HF Spaces compatibility (they manage scaling)
CMD uvicorn negotiation_env.server.app:app --host ${HOST} --port ${PORT} --workers ${WORKERS}
