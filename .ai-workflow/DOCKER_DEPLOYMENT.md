# Docker Deployment Guide for NegotiationEnv

## Overview

The NegotiationEnv server is containerized following OpenEnv best practices. This guide provides the exact commands needed for building and running the environment per hackathon requirements.

## Prerequisites

- Docker installed and running
- Repository cloned to local machine

## Build Commands

### Standard Build (from repository root)

```bash
cd /path/to/NegotiatoRL
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

**Important**: 
- Build context is the repository root (`.`)
- Dockerfile path is `negotiation_env/server/Dockerfile`
- This ensures the package `negotiation_env` is properly copied into the container

### Build with Custom Tag

```bash
docker build -t negotiation-env:v1.0.0 -f negotiation_env/server/Dockerfile .
```

### Build for Hugging Face Space Registry

```bash
docker build -t registry.hf.space/YOUR-USERNAME-negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

## Run Commands

### Basic Run (default configuration)

```bash
docker run -d -p 8000:8000 negotiation-env:latest
```

This starts the server with:
- Host: `0.0.0.0`
- Port: `8000`
- Workers: `4`
- Max concurrent environments: `100` (default)

### Run with Custom Environment Variables

```bash
docker run -d -p 8000:8000 \
    -e HOST=0.0.0.0 \
    -e PORT=8000 \
    -e WORKERS=4 \
    -e MAX_CONCURRENT_ENVS=100 \
    --name negotiation-env-server \
    negotiation-env:latest
```

### Run with Logs (foreground mode)

```bash
docker run -p 8000:8000 \
    -e WORKERS=2 \
    negotiation-env:latest
```

### Run on Different Port

```bash
docker run -d -p 9000:9000 \
    -e PORT=9000 \
    negotiation-env:latest
```

## Using `uv` Commands (Local Development)

If you prefer using `uv` for local development instead of Docker:

### Install Dependencies

```bash
cd negotiation_env
uv sync
```

### Run Server (Development Mode with Auto-Reload)

```bash
uv run server
```

This executes: `uvicorn negotiation_env.server.app:app --host 0.0.0.0 --port 8000 --reload`

### Run Tests

```bash
uv run test
```

## Validation Commands

### Check Container Health

```bash
# Wait a few seconds after starting, then:
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

### Test WebSocket Connection

```bash
# From Python:
python -c "
from negotiation_env import NegotiationEnv
env = NegotiationEnv(base_url='http://localhost:8000').sync()
result = env.reset()
print(f'Reset successful: {result.observation.message}')
"
```

### View API Documentation

```bash
# Open in browser:
open http://localhost:8000/docs
```

### Check Container Logs

```bash
docker logs -f <container_id>
```

### Verify Import Path Resolution

```bash
# Inside running container:
docker exec -it <container_id> python -c "from negotiation_env.server.app import app; print('✓ Import successful')"
```

## Container Management

### List Running Containers

```bash
docker ps | grep negotiation-env
```

### Stop Container

```bash
docker stop <container_id>
```

### Remove Container

```bash
docker rm <container_id>
```

### Remove Image

```bash
docker rmi negotiation-env:latest
```

### View Container Resource Usage

```bash
docker stats <container_id>
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `WORKERS` | `4` | Uvicorn worker processes |
| `MAX_CONCURRENT_ENVS` | `100` | Max WebSocket sessions |

## Deployment to Hugging Face Spaces

### Using OpenEnv CLI

```bash
cd negotiation_env
openenv push --repo-id YOUR-USERNAME/negotiation-env
```

This automatically:
1. Builds the Docker image
2. Pushes to HF Space registry
3. Deploys the environment

Your environment will be live at:
- **API endpoint**: `https://YOUR-USERNAME-negotiation-env.hf.space`
- **Web UI**: `https://YOUR-USERNAME-negotiation-env.hf.space/web`
- **API docs**: `https://YOUR-USERNAME-negotiation-env.hf.space/docs`
- **Health check**: `https://YOUR-USERNAME-negotiation-env.hf.space/health`

### Manual Docker Push

```bash
# Build with HF registry tag
docker build -t registry.hf.space/YOUR-USERNAME-negotiation-env:latest -f negotiation_env/server/Dockerfile .

# Login to HF registry
docker login registry.hf.space -u YOUR-USERNAME

# Push
docker push registry.hf.space/YOUR-USERNAME-negotiation-env:latest
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'negotiation_env'`

**Solution**: Ensure you're building from the repository root:
```bash
# WRONG (from negotiation_env/)
cd negotiation_env
docker build -t negotiation-env:latest -f server/Dockerfile .

# CORRECT (from repo root)
cd /path/to/NegotiatoRL
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

### Health Check Failing

**Problem**: Container starts but health check fails

**Solution**: Check that curl is installed in the container and port is correct:
```bash
docker exec -it <container_id> curl http://localhost:8000/health
```

### Port Already in Use

**Problem**: `Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use`

**Solution**: Use a different host port:
```bash
docker run -d -p 8001:8000 negotiation-env:latest
```

### Worker Process Issues

**Problem**: Out of memory or slow performance

**Solution**: Reduce workers or increase container resources:
```bash
docker run -d -p 8000:8000 \
    -e WORKERS=2 \
    --memory="2g" \
    negotiation-env:latest
```

## Build Optimizations

### Multi-Stage Build (Future Enhancement)

For smaller image sizes, consider multi-stage builds:

```dockerfile
# Builder stage
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --user "openenv-core>=0.1.0" ...

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
...
```

### Layer Caching

The current Dockerfile is optimized for layer caching:
1. System dependencies (rarely change)
2. Python dependencies (change occasionally)
3. Application code (changes frequently)

Rebuilds will reuse cached layers when possible.

## Production Checklist

- [ ] Build completes without errors
- [ ] Container starts successfully
- [ ] Health check endpoint responds
- [ ] WebSocket endpoint accepts connections
- [ ] Client can successfully `reset()` and `step()`
- [ ] API documentation loads at `/docs`
- [ ] Logs show no import errors
- [ ] Resource limits configured appropriately
- [ ] Secrets (if any) managed via environment variables, not baked into image

## References

- OpenEnv Documentation: [Module 3 - Deploying Environments](../Information/README3.md)
- Hackathon Requirements: [Information/](../Information/)
- Package Configuration: [negotiation_env/pyproject.toml](../negotiation_env/pyproject.toml)
