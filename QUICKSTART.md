# NegotiationRL - Quick Start Guide

## Helper Scripts

All scripts are located at the repo root and are ready to use:

### 0. Check Environment (RECOMMENDED FIRST STEP)

```bash
# Check local environment only
./check_env.sh

# Check local environment + local server
./check_env.sh http://localhost:8000

# Check local environment + HuggingFace Space
./check_env.sh https://your-space.hf.space
```

**What it validates:**
- Docker installed and daemon running
- Required files exist (Dockerfile, openenv.yaml, inference.py, .env)
- Docker build succeeds
- openenv validate passes (or warns about known issues)
- HuggingFace Space is live and responds to /reset (if URL provided)

This script matches the requirements from `Information/pre-validation.py` and helps catch issues before submission.

### 1. Run Inference (Baseline Evaluation)

```bash
# Run all 3 tasks (local testing)
./run_inference.sh

# Run a specific task (evaluator mode)
./run_inference.sh easy_conceder
./run_inference.sh medium_tft
./run_inference.sh hard_hardliner
```

**Requirements:**
- Set environment variables in `.env` (or export them)
- Docker image must be running (see below)

### 2. Run Tests

```bash
./run_tests.sh
```

Runs the full test suite (25 tests). All must pass before submission.

### 3. Start Local Server

```bash
./run_server.sh
```

Starts the negotiation environment server at `http://localhost:8000`

**Endpoints:**
- `/health` - Health check
- `/docs` - API documentation
- `/reset` - Initialize episode
- `/state` - Get current state

### 4. Pre-Submission Validation

```bash
./validate.sh
```

Runs all hackathon checklist validations:
- ✓ File structure
- ✓ Environment configuration
- ✓ OpenEnv spec compliance
- ✓ Grader functions
- ✓ Log format
- ✓ Tests passing
- ✓ Documentation

**Run this before submitting!**

---

## Environment Configuration

Edit `.env` file in repo root:

```bash
# Required for inference
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
HF_TOKEN=your-token-here
IMAGE_NAME=negotiation-env:latest
```

---

## Docker Quick Reference

### Build Image

```bash
docker build -t negotiation-env:latest \
  -f negotiation_env/negotiation_env/server/Dockerfile .
```

### Run Container

```bash
docker run -d -p 8000:8000 \
  -e WORKERS=4 \
  negotiation-env:latest
```

### Test Container

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

---

## Workflow

### Development Workflow

1. **Make changes** to code
2. **Run tests**: `./run_tests.sh`
3. **Start server**: `./run_server.sh` (test endpoints)
4. **Build Docker**: `docker build ...`
5. **Test inference**: `./run_inference.sh`

### Pre-Submission Workflow

1. **Run validation**: `./validate.sh`
2. **Fix any failures**
3. **Test inference** with all 3 tasks
4. **Build final Docker image**
5. **Push to Hugging Face Space**
6. **Submit**

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"

**Solution:** Use the helper scripts instead of running Python directly
```bash
./run_inference.sh  # NOT: python3 inference.py
```

### "OpenAIError: The api_key client option must be set"

**Solution:** Set HF_TOKEN in `.env` file
```bash
echo "HF_TOKEN=your-token-here" >> .env
```

### "can't open file 'inference.py'"

**Solution:** Run scripts from repo root
```bash
cd /path/to/NegotiatoRL
./run_inference.sh
```

### Docker build fails

**Solution:** Build from repo root with correct Dockerfile path
```bash
docker build -t negotiation-env:latest \
  -f negotiation_env/negotiation_env/server/Dockerfile .
```

---

## Pre-Submission Checklist

- [ ] All tests pass: `./run_tests.sh`
- [ ] Validation passes: `./validate.sh`
- [ ] `.env` configured with real values
- [ ] Inference runs without errors
- [ ] All 3 tasks produce scores in [0.0, 1.0]
- [ ] Docker builds successfully
- [ ] Docker runs and responds to `/health`
- [ ] README.md has no placeholders
- [ ] Code committed to git

---

## File Structure

```
NegotiatoRL/
├── inference.py              ← Main entry point (repo root)
├── .env                      ← Environment config
├── run_inference.sh          ← Run inference helper
├── run_tests.sh              ← Run tests helper
├── run_server.sh             ← Run server helper
├── validate.sh               ← Pre-submission validator
├── README.md                 ← Documentation
└── negotiation_env/          ← Package directory
    ├── openenv.yaml          ← OpenEnv spec
    ├── pyproject.toml        ← Dependencies
    └── negotiation_env/      ← Python package
        ├── graders.py        ← Grader functions
        ├── models.py         ← Data models
        ├── rewards.py        ← Reward functions
        ├── strategies.py     ← Opponent strategies
        ├── test_env.py       ← Test suite
        └── server/
            ├── Dockerfile    ← Container config
            ├── app.py        ← FastAPI app
            └── environment.py ← Core environment
```

---

## Quick Commands

```bash
# Run everything locally
./run_tests.sh && ./run_server.sh &
./run_inference.sh

# Pre-submission check
./validate.sh

# Build and test Docker
docker build -t negotiation-env:latest -f negotiation_env/negotiation_env/server/Dockerfile .
docker run -d -p 8000:8000 negotiation-env:latest
curl http://localhost:8000/health
```
