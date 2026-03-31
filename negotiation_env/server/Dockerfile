# ============================================================================
# Dockerfile for NegotiationEnv Server
# ============================================================================
# 
# Build:
#   docker build -t negotiation-env:latest -f server/Dockerfile .
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
# ============================================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir \
    openenv-core>=0.1.0 \
    pydantic>=2.0.0 \
    fastapi>=0.100.0 \
    uvicorn>=0.23.0 \
    websockets>=11.0

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONPATH="/app:$PYTHONPATH"
ENV HOST="0.0.0.0"
ENV PORT="8000"
ENV WORKERS="4"

# Expose the port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the server
CMD ["sh", "-c", "uvicorn server.app:app --host ${HOST} --port ${PORT} --workers ${WORKERS}"]
