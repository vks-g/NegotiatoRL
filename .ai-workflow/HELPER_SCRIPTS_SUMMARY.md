# Helper Scripts Created ✅

Four executable helper scripts have been created at the repo root to streamline development and submission:

## 📋 Scripts

### 1. `run_inference.sh` - Run Baseline Inference

**Purpose**: Execute inference.py with proper environment setup

**Usage**:
```bash
# Run all 3 tasks (local testing mode)
./run_inference.sh

# Run single task (evaluator mode)
./run_inference.sh easy_conceder
./run_inference.sh medium_tft  
./run_inference.sh hard_hardliner
```

**Features**:
- ✅ Loads variables from `.env` automatically
- ✅ Validates required environment variables
- ✅ Uses `uv run` with correct virtual environment
- ✅ Supports both single-task and multi-task modes
- ✅ Color-coded output for easy reading

**Requirements**:
- `.env` file with `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`, `IMAGE_NAME`
- Docker image must be running (for `NegotiationEnv.from_docker_image()`)

---

### 2. `run_tests.sh` - Run Test Suite

**Purpose**: Execute all 25 tests to verify environment correctness

**Usage**:
```bash
./run_tests.sh
```

**Tests**:
- Episode completion (4 tests)
- Reward bounds (4 tests)
- Grader completeness (3 tests)
- Reproducibility (3 tests)
- Strategy behavior (3 tests)
- Utility computation (3 tests)
- Observation structure (2 tests)
- HTTP integration (3 tests)

**Total**: 25 tests - all must pass

---

### 3. `run_server.sh` - Start Local Server

**Purpose**: Start the NegotiationEnv HTTP server locally for testing

**Usage**:
```bash
./run_server.sh
```

**Server runs at**: `http://localhost:8000`

**Endpoints**:
- `/health` - Health check
- `/docs` - OpenAPI documentation
- `/reset` - Initialize new episode
- `/step` - Execute action (stateless)
- `/state` - Get current state

---

### 4. `validate.sh` - Pre-Submission Validator

**Purpose**: Run all hackathon checklist validations before submitting

**Usage**:
```bash
./validate.sh
```

**Checks** (10 validation categories):
1. ✓ inference.py at repo root
2. ✓ .env configuration (API_BASE_URL, MODEL_NAME, HF_TOKEN, IMAGE_NAME)
3. ✓ openenv.yaml with 3 tasks and grader functions
4. ✓ Dockerfile with correct PYTHONPATH
5. ✓ Grader functions (easy, medium, hard)
6. ✓ OpenAI client usage and sys.path fix
7. ✓ [START]/[STEP]/[END] log format with .3f score precision
8. ✓ All 25 tests passing
9. ✓ Python imports working
10. ✓ README.md documentation

**Exit codes**:
- `0` = All checks passed, ready to submit
- `1` = Some checks failed, fix before submitting

---

## 📖 Additional Documentation

### `QUICKSTART.md`

Complete quick reference guide including:
- Helper script usage
- Environment configuration
- Docker commands
- Development workflow
- Pre-submission workflow
- Troubleshooting
- File structure reference

---

## ⚙️ Environment Setup

All scripts expect a `.env` file at repo root with:

```bash
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
HF_TOKEN=your-huggingface-token
IMAGE_NAME=negotiation-env:latest
```

**Current .env status**: ✅ Configured with real HF_TOKEN

---

## 🎯 Pre-Submission Workflow

1. **Run validation**:
   ```bash
   ./validate.sh
   ```

2. **Fix any failures** (if validation fails)

3. **Run all tests**:
   ```bash
   ./run_tests.sh
   ```

4. **Test inference** (requires Docker image running):
   ```bash
   ./run_inference.sh easy_conceder
   ```

5. **Build Docker image**:
   ```bash
   docker build -t negotiation-env:latest \
     -f negotiation_env/negotiation_env/server/Dockerfile .
   ```

6. **Test Docker**:
   ```bash
   docker run -d -p 8000:8000 negotiation-env:latest
   curl http://localhost:8000/health
   ```

7. **Push to Hugging Face Space** and **Submit**

---

## ✅ Validation Results

**Quick check** (just ran):
1. ✓ inference.py exists
2. ✓ .env exists  
3. ✓ openenv.yaml exists
4. ✓ Dockerfile exists
5. ✓ graders.py exists
6. ✓ Helper scripts exist

**Tests**: 25/25 passing ✅

**Grader functions**: All 3 implemented ✅

**Log format**: [START]/[STEP]/[END] with score:.3f ✅

---

## 🚨 Common Issues

### Issue: `ModuleNotFoundError: No module named 'openai'`

**Solution**: Use helper scripts instead of direct Python
```bash
./run_inference.sh  # NOT: python3 inference.py
```

### Issue: `OpenAIError: api_key must be set`

**Solution**: Set HF_TOKEN in .env
```bash
echo "HF_TOKEN=your-token-here" >> .env
```

### Issue: `can't open file 'inference.py'`

**Solution**: Run from repo root
```bash
cd /Users/gokulvks/Documents/NegotiatoRL
./run_inference.sh
```

---

## 📁 Files Created

| File | Purpose | Executable |
|------|---------|------------|
| `run_inference.sh` | Run inference.py | ✅ |
| `run_tests.sh` | Run test suite | ✅ |
| `run_server.sh` | Start local server | ✅ |
| `validate.sh` | Pre-submission check | ✅ |
| `QUICKSTART.md` | Quick reference guide | - |

All scripts are ready to use and follow hackathon submission guidelines.
