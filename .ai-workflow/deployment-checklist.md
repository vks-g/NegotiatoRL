# Pre-Deployment Checklist - NegotiationEnv
**Meta PyTorch OpenEnv Hackathon Submission**

---

## 🎯 Phase 1: Local Build & Test

### Build Verification
- [ ] Build completes without errors from repo root
  ```bash
  cd /Users/gokulvks/Documents/NegotiatoRL
  docker build -t negotiation-env:test -f negotiation_env/server/Dockerfile .
  ```
- [ ] Image size is reasonable (< 500 MB)
  ```bash
  docker images negotiation-env:test
  ```
- [ ] No security vulnerabilities (if scanner available)
  ```bash
  docker scan negotiation-env:test
  ```

### Runtime Verification
- [ ] Container starts successfully
  ```bash
  docker run -d -p 8000:8000 --name test-env negotiation-env:test
  ```
- [ ] Container runs as non-root user
  ```bash
  docker exec test-env whoami  # Expected: appuser
  ```
- [ ] Health check passes within 10 seconds
  ```bash
  sleep 10 && curl http://localhost:8000/health
  ```
- [ ] No errors in logs
  ```bash
  docker logs test-env
  ```

### Endpoint Verification
- [ ] `/health` endpoint responds
  ```bash
  curl http://localhost:8000/health
  ```
- [ ] `/docs` endpoint accessible
  ```bash
  curl -I http://localhost:8000/docs  # Expect 200 OK
  ```
- [ ] OpenAPI spec available
  ```bash
  curl http://localhost:8000/openapi.json | jq '.paths | keys'
  # Should show: ["/health", "/reset", "/state", "/step", "/ws"]
  ```
- [ ] WebSocket endpoint available (if wscat installed)
  ```bash
  wscat -c ws://localhost:8000/ws
  ```

### OpenEnv API Verification
- [ ] `/reset` endpoint works
  ```bash
  curl -X POST http://localhost:8000/reset
  ```
- [ ] `/state` endpoint works
  ```bash
  curl http://localhost:8000/state
  ```
- [ ] `/step` endpoint works (after reset)
  ```bash
  curl -X POST http://localhost:8000/step \
    -H "Content-Type: application/json" \
    -d '{"offer": {"price": 100, "quantity": 10}}'
  ```

### Cleanup
- [ ] Stop and remove test container
  ```bash
  docker stop test-env && docker rm test-env
  ```

---

## 🎯 Phase 2: Code Quality

### File Structure
- [ ] All required files present:
  - `negotiation_env/__init__.py`
  - `negotiation_env/models.py`
  - `negotiation_env/client.py`
  - `negotiation_env/server/app.py`
  - `negotiation_env/server/environment.py`
  - `negotiation_env/server/Dockerfile`

### Import Verification
- [ ] No circular imports
  ```bash
  docker run --rm negotiation-env:test python -c "from negotiation_env.server.app import app"
  ```
- [ ] All relative imports work
  ```bash
  docker run --rm negotiation-env:test python -c "from negotiation_env.models import NegotiationAction"
  ```

### Dependencies
- [ ] All dependencies in pyproject.toml
- [ ] No missing dependencies in Dockerfile
- [ ] Version pins appropriate (>= not ==)

---

## 🎯 Phase 3: Hackathon Compliance

### OpenEnv Integration
- [ ] Environment extends `openenv.core.Env`
- [ ] Action model is Pydantic BaseModel
- [ ] Observation model is Pydantic BaseModel
- [ ] FastAPI app created via `create_fastapi_app()`

### Logging Format (Client-Side - inference.py)
- [ ] `[START]` line format correct
- [ ] `[STEP]` line format correct
- [ ] `[END]` line format correct
- [ ] Rewards formatted to 2 decimals
- [ ] Score normalized to [0, 1]

### Docker Integration
- [ ] Environment works with `from_docker_image()`
- [ ] Container name/tag is appropriate
- [ ] Port 8000 exposed and working

---

## 🎯 Phase 4: Hugging Face Spaces

### Repository Preparation
- [ ] `.dockerignore` present and correct
- [ ] `.gitignore` doesn't exclude necessary files
- [ ] README.md updated with deployment instructions
- [ ] LICENSE file present (if required)

### Dockerfile Configuration
- [ ] Dockerfile path: `negotiation_env/server/Dockerfile`
- [ ] Build context: repository root (`.`)
- [ ] Port exposed: `8000`
- [ ] Health check configured

### HF Spaces Settings
- [ ] Space created with "Docker" runtime
- [ ] Dockerfile path set: `negotiation_env/server/Dockerfile`
- [ ] Port set to `8000`
- [ ] Environment variables configured (if needed)

### Deployment Test
- [ ] Code pushed to HF Spaces repo
  ```bash
  git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/negotiation-env
  git push hf main
  ```
- [ ] HF Spaces build succeeds
- [ ] Space is accessible online
- [ ] Health check passes on deployed Space

---

## 🎯 Phase 5: Integration Testing

### Client Library Test
- [ ] Install client library in separate environment
- [ ] Connect to deployed server
- [ ] Run reset/step/state cycle
- [ ] WebSocket connection works

### Inference Script Test
- [ ] `inference.py` runs without errors
- [ ] Connects to container successfully
- [ ] Completes full episode
- [ ] Outputs correct log format

### Load Testing (Optional)
- [ ] Multiple concurrent connections work
- [ ] Memory usage stays bounded
- [ ] No connection leaks
- [ ] Proper cleanup on disconnect

---

## 🎯 Phase 6: Documentation

### Code Documentation
- [ ] README.md updated
- [ ] API documentation in `/docs` endpoint
- [ ] Example usage provided
- [ ] Environment variables documented

### Deployment Documentation
- [ ] Build instructions clear
- [ ] Run instructions provided
- [ ] Troubleshooting guide available
- [ ] HF Spaces deployment steps documented

### Hackathon Specific
- [ ] submission requirements met
- [ ] Environment description clear
- [ ] Reward structure documented
- [ ] Action/observation space defined

---

## 🎯 Phase 7: Final Checks

### Performance
- [ ] Cold start < 10 seconds
- [ ] Reset latency < 100ms
- [ ] Step latency < 200ms
- [ ] Memory usage < 512 MB
- [ ] No memory leaks over 100 episodes

### Security
- [ ] No secrets in Dockerfile
- [ ] No secrets in git history
- [ ] Container runs as non-root
- [ ] No unnecessary ports exposed

### Reliability
- [ ] Health checks passing
- [ ] Proper error handling
- [ ] Graceful shutdown works
- [ ] Container restarts cleanly

### Hackathon Submission
- [ ] All required files submitted
- [ ] Docker image publicly accessible
- [ ] Documentation complete
- [ ] Demo/example provided
- [ ] Submission deadline noted

---

## 🚨 Common Issues & Solutions

### Issue: Build fails with "COPY failed"
**Cause**: Building from wrong directory
**Solution**: Always build from repo root
```bash
cd /Users/gokulvks/Documents/NegotiatoRL  # Repo root
docker build -f negotiation_env/server/Dockerfile .
```

### Issue: "Module not found: negotiation_env"
**Cause**: PYTHONPATH not set
**Solution**: Verify Dockerfile has:
```dockerfile
ENV PYTHONPATH="/app:$PYTHONPATH"
```

### Issue: Health check fails
**Cause**: App not ready or wrong port
**Solution**: Check logs and increase `--start-period`:
```dockerfile
HEALTHCHECK --start-period=15s ...
```

### Issue: HF Spaces build fails
**Cause**: Wrong Dockerfile path
**Solution**: Set in Space settings: `negotiation_env/server/Dockerfile`

### Issue: WebSocket connection fails
**Cause**: Uvicorn workers > 1
**Solution**: Set `WORKERS=1` in Dockerfile

---

## ✅ Sign-Off

### Developer
- [ ] I have tested all endpoints locally
- [ ] I have verified the build process
- [ ] I have reviewed the documentation
- [ ] Code is ready for deployment

**Name**: _________________  
**Date**: _________________

### DevOps/Ops
- [ ] Dockerfile follows best practices
- [ ] Security hardening complete
- [ ] Performance benchmarks met
- [ ] Monitoring/logging configured

**Name**: @ops  
**Date**: 2026-04-05

### Hackathon Submission
- [ ] All requirements met
- [ ] Demo/example tested
- [ ] Documentation complete
- [ ] Ready for submission

**Name**: _________________  
**Date**: _________________

---

## 📋 Submission Package

Include the following in your hackathon submission:

1. **Source Code**
   - [ ] `negotiation_env/` directory (complete package)
   - [ ] `inference.py` (hackathon entry point)
   - [ ] `README.md` (documentation)

2. **Docker**
   - [ ] `negotiation_env/server/Dockerfile` (deployment)
   - [ ] `.dockerignore` (build optimization)
   - [ ] Docker image name/tag documented

3. **Documentation**
   - [ ] Environment description
   - [ ] Action/observation space specification
   - [ ] Reward structure explanation
   - [ ] Example usage

4. **Deployment**
   - [ ] HF Spaces URL (if deployed)
   - [ ] Docker Hub URL (if applicable)
   - [ ] Deployment instructions

5. **Testing**
   - [ ] Example inference script
   - [ ] Test results/logs
   - [ ] Performance benchmarks

---

**Checklist Version**: 1.0  
**Last Updated**: 2026-04-05  
**Maintainer**: @ops

**Ready for deployment when all Phase 1-7 items are checked ✅**
