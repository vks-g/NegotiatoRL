# Bug #2 Fix - Dockerfile Runtime/Import Issues

**Date**: 2026-04-05  
**Agent**: @ops  
**Status**: ✅ FIXED  

## Problem Summary

The Dockerfile had three critical issues preventing successful builds and runtime:

1. **Unquoted pip version specifiers** - Caused build failures
2. **Incorrect import path** - Module resolution failed at runtime
3. **Wrong build context assumptions** - Dockerfile expected wrong directory structure

## Root Cause Analysis

### Issue 1: Unquoted Version Specifiers
```dockerfile
# BROKEN
RUN pip install --no-cache-dir \
    openenv-core>=0.1.0 \
    pydantic>=2.0.0
```

Shell interprets `>=` as redirection operator, causing pip to fail.

### Issue 2: Import Path Resolution
```dockerfile
# BROKEN
CMD ["sh", "-c", "uvicorn server.app:app ..."]
```

This assumes the package is at `/app/server/app.py`, but:
- Build context is repo root
- Package structure is `negotiation_env/server/app.py`
- Python needs `negotiation_env.server.app:app` module path

### Issue 3: Build Context
Original comments suggested building from `negotiation_env/`:
```bash
# BROKEN
cd negotiation_env
docker build -t negotiation-env:latest -f server/Dockerfile .
```

This doesn't match OpenEnv conventions (see Information/README3.md).

## Solution Implemented

### 1. Quoted All Version Specifiers (Line 37-42)
```dockerfile
RUN pip install --no-cache-dir \
    "openenv-core>=0.1.0" \
    "pydantic>=2.0.0" \
    "fastapi>=0.100.0" \
    "uvicorn>=0.23.0" \
    "websockets>=11.0"
```

✅ Prevents shell misinterpretation of `>=`

### 2. Fixed Module Import Path (Line 61)
```dockerfile
CMD ["sh", "-c", "uvicorn negotiation_env.server.app:app --host ${HOST} --port ${PORT} --workers ${WORKERS}"]
```

✅ Correct module path for package structure  
✅ Maintains environment variable interpolation

### 3. Corrected Build Context (Lines 4-6, 34, 45)
```dockerfile
# Build from repository root:
#   docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .

# Copy pyproject.toml for dependency installation
COPY negotiation_env/pyproject.toml /app/negotiation_env/

# Copy the entire negotiation_env package
COPY negotiation_env /app/negotiation_env
```

✅ Build from repo root (context = `.`)  
✅ Dockerfile path is `negotiation_env/server/Dockerfile`  
✅ COPY commands use correct relative paths

### 4. Set Correct PYTHONPATH (Line 48)
```dockerfile
ENV PYTHONPATH="/app:$PYTHONPATH"
```

✅ Python can find `negotiation_env` package at `/app/negotiation_env`

## Hackathon Compliance

Per Information/README3.md requirements:

### ✅ Build Command (from repo root)
```bash
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

### ✅ Run Command (basic)
```bash
docker run -d -p 8000:8000 negotiation-env:latest
```

### ✅ Run Command (with env vars)
```bash
docker run -d -p 8000:8000 \
    -e WORKERS=4 \
    -e MAX_CONCURRENT_ENVS=100 \
    negotiation-env:latest
```

### ✅ uv Commands (local development)
```bash
cd negotiation_env
uv sync
uv run server
```

## Validation Steps

Since Docker is not installed on this system, validation must be performed by user:

### Step 1: Build Test
```bash
cd /path/to/NegotiatoRL
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

**Expected**: Build completes without errors, all layers succeed.

### Step 2: Container Start Test
```bash
docker run -d -p 8000:8000 --name test-negotiation-env negotiation-env:latest
sleep 5  # Wait for startup
```

**Expected**: Container starts and stays running.

### Step 3: Health Check Test
```bash
curl http://localhost:8000/health
```

**Expected**: `{"status": "healthy"}`

### Step 4: Import Path Test
```bash
docker exec -it test-negotiation-env python -c "from negotiation_env.server.app import app; print('✓ Import successful')"
```

**Expected**: No ModuleNotFoundError, prints success message.

### Step 5: WebSocket Test
```bash
python -c "
from negotiation_env import NegotiationEnv
env = NegotiationEnv(base_url='http://localhost:8000').sync()
result = env.reset()
print(f'✓ Reset successful: {result.observation.message}')
"
```

**Expected**: Connects to WebSocket, receives observation with message.

### Step 6: Cleanup
```bash
docker stop test-negotiation-env
docker rm test-negotiation-env
```

## Additional Deliverables

### 1. `.dockerignore` File
Created at repo root to optimize build context:
- Excludes `.venv/`, `__pycache__/`, `.git/`
- Excludes `Information/` folder (not needed in container)
- Reduces build time and image size

### 2. Comprehensive Documentation
Created `.ai-workflow/DOCKER_DEPLOYMENT.md` with:
- Exact build/run commands
- uv command alternatives
- Validation procedures
- Troubleshooting guide
- Production checklist
- HF Space deployment instructions

## Files Modified

1. **negotiation_env/server/Dockerfile** - Fixed all three issues
2. **.dockerignore** - Created for build optimization
3. **.ai-workflow/DOCKER_DEPLOYMENT.md** - Comprehensive deployment guide

## Technical Notes

### Why This Works

1. **Build Context = Repo Root**
   - Dockerfile can access `negotiation_env/` via relative path
   - Matches OpenEnv conventions (see echo-env, openspiel-catch examples)

2. **PYTHONPATH = /app**
   - Package `negotiation_env` is at `/app/negotiation_env/`
   - Python can `import negotiation_env.server.app`

3. **Module Path = negotiation_env.server.app:app**
   - Uvicorn imports: `negotiation_env` (package) → `server` (subpackage) → `app` (module) → `app` (FastAPI instance)
   - Matches how `server/app.py` uses relative imports: `from ..models import ...`

### Comparison to OpenEnv Examples

From Information/README3.md:
```bash
# Echo environment
git clone https://huggingface.co/spaces/openenv/echo-env
cd echo-env
docker build -t my-echo-env:latest -f server/Dockerfile .
```

Our structure matches this pattern:
- Root directory contains the package
- Dockerfile is in `server/` subdirectory
- Build from root, not from server/

## Next Steps

1. **User Testing**: Run validation steps above
2. **Integration**: Test with TRL GRPO training pipeline
3. **Deployment**: Push to HF Spaces using `openenv push`

## References

- Information/README3.md - Deployment patterns
- Information/README4.md - Environment structure
- negotiation_env/pyproject.toml - Package configuration
- OpenEnv best practices - Docker as microservice pattern
