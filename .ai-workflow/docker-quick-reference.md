# Docker Quick Reference - NegotiationEnv
**For Meta PyTorch OpenEnv Hackathon Submission**

---

## 🚀 Quick Start

### Build
```bash
cd /Users/gokulvks/Documents/NegotiatoRL
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

### Run
```bash
docker run -d -p 8000:8000 --name negotiation-env negotiation-env:latest
```

### Test
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"} or similar
```

### Stop
```bash
docker stop negotiation-env && docker rm negotiation-env
```

---

## 📦 Common Commands

### Build with tag for HF Spaces
```bash
docker build -t negotiation-env:v1.0.0 -f negotiation_env/server/Dockerfile .
```

### Run with custom port
```bash
docker run -d -p 9000:8000 -e PORT=8000 --name negotiation-env negotiation-env:latest
```

### Run with increased workers (local only)
```bash
docker run -d -p 8000:8000 -e WORKERS=4 --name negotiation-env negotiation-env:latest
```

### View logs
```bash
docker logs -f negotiation-env
```

### Shell into container (debugging)
```bash
docker run -it --rm negotiation-env:latest /bin/bash
```

### Check container health
```bash
docker inspect --format='{{.State.Health.Status}}' negotiation-env
```

---

## 🧪 Testing Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### OpenAPI Docs
```bash
# In browser
open http://localhost:8000/docs

# Or get JSON
curl http://localhost:8000/openapi.json | jq
```

### WebSocket Test (using wscat)
```bash
npm install -g wscat
wscat -c ws://localhost:8000/ws
```

### Reset Environment
```bash
curl -X POST http://localhost:8000/reset
```

---

## 🏗️ Build Troubleshooting

### "No such file or directory" during build
**Problem**: Building from wrong directory

**Solution**:
```bash
# ✅ CORRECT - from repo root
cd /Users/gokulvks/Documents/NegotiatoRL
docker build -f negotiation_env/server/Dockerfile .

# ❌ WRONG - from negotiation_env/
cd /Users/gokulvks/Documents/NegotiatoRL/negotiation_env
docker build -f server/Dockerfile .  # This will fail!
```

### "Module not found" when running
**Problem**: PYTHONPATH not set correctly

**Solution**: Rebuild with latest Dockerfile (fixed)

### Build cache issues
```bash
# Force rebuild without cache
docker build --no-cache -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

---

## 🌐 Hugging Face Spaces Deployment

### Option 1: Let HF Build
1. Create Docker Space on HF
2. In Space settings, set Dockerfile path: `negotiation_env/server/Dockerfile`
3. Push code to HF:
```bash
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/negotiation-env
git push hf main
```

### Option 2: Pre-built Image
```bash
# Build
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .

# Tag for HF registry
docker tag negotiation-env:latest registry.huggingface.co/YOUR_USERNAME/negotiation-env:latest

# Login to HF Container Registry
docker login registry.huggingface.co -u YOUR_USERNAME -p YOUR_HF_TOKEN

# Push
docker push registry.huggingface.co/YOUR_USERNAME/negotiation-env:latest
```

---

## 📊 Resource Limits (Production)

### With memory limit
```bash
docker run -d \
  --memory="512m" \
  --memory-swap="512m" \
  -p 8000:8000 \
  negotiation-env:latest
```

### With CPU limit
```bash
docker run -d \
  --cpus="1.0" \
  -p 8000:8000 \
  negotiation-env:latest
```

### Both (recommended for production)
```bash
docker run -d \
  --memory="512m" \
  --cpus="1.0" \
  --pids-limit=100 \
  -p 8000:8000 \
  --name negotiation-env \
  negotiation-env:latest
```

---

## 🔍 Debugging

### Check PYTHONPATH
```bash
docker run --rm negotiation-env:latest env | grep PYTHON
```

### List files in container
```bash
docker run --rm negotiation-env:latest ls -la /app/negotiation_env/
```

### Test import manually
```bash
docker run -it --rm negotiation-env:latest python -c "from negotiation_env.server.app import app; print('OK')"
```

### Check running processes
```bash
docker exec negotiation-env ps aux
```

### Get container IP
```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' negotiation-env
```

---

## 🧹 Cleanup

### Remove container
```bash
docker rm -f negotiation-env
```

### Remove image
```bash
docker rmi negotiation-env:latest
```

### Remove all unused images
```bash
docker image prune -a
```

### Complete cleanup
```bash
docker rm -f negotiation-env
docker rmi negotiation-env:latest
docker system prune -a
```

---

## 📝 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Server port |
| `WORKERS` | `1` | Uvicorn workers (HF Spaces: keep at 1) |
| `PYTHONPATH` | `/app` | Python module search path |
| `PYTHONUNBUFFERED` | `1` | Real-time logging |
| `MAX_CONCURRENT_ENVS` | (optional) | Limit concurrent environments |

### Override example
```bash
docker run -d \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  -e WORKERS=2 \
  -e MAX_CONCURRENT_ENVS=50 \
  -p 8000:8000 \
  negotiation-env:latest
```

---

## ⚡ Performance Tips

### Use BuildKit (faster builds)
```bash
DOCKER_BUILDKIT=1 docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .
```

### Multi-platform build (for HF Spaces)
```bash
docker buildx build \
  --platform linux/amd64 \
  -t negotiation-env:latest \
  -f negotiation_env/server/Dockerfile \
  .
```

### Check image size
```bash
docker images negotiation-env:latest
```

### Layer analysis
```bash
docker history negotiation-env:latest
```

---

## 🔒 Security

### Scan for vulnerabilities
```bash
docker scan negotiation-env:latest
```

### Run as read-only (advanced)
```bash
docker run -d \
  --read-only \
  --tmpfs /tmp \
  -p 8000:8000 \
  negotiation-env:latest
```

### Verify non-root user
```bash
docker run --rm negotiation-env:latest whoami
# Expected: appuser
```

---

## 📚 Additional Resources

- OpenEnv Docs: https://github.com/pytorch/openenv
- FastAPI Docs: https://fastapi.tiangolo.com
- Uvicorn Docs: https://www.uvicorn.org
- Docker Best Practices: https://docs.docker.com/develop/dev-best-practices/
- HF Spaces: https://huggingface.co/docs/hub/spaces-overview

---

**Last Updated**: 2026-04-05  
**Maintainer**: @ops
