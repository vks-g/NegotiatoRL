# NegotiationRL

A production-grade **multi-issue bilateral negotiation RL environment** for training LLMs on complex negotiation tasks. Built on the [OpenEnv](https://github.com/meta-pytorch/openenv) framework for OpenAI Gym-like simplicity with Docker-based isolation, WebSocket APIs, and native TRL/GRPO integration.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Docker (for containerized deployment)
- Hugging Face API token (for LLM inference)

### 1. Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-org/NegotiationRL
cd NegotiationRL

# Install dependencies with uv (recommended)
uv sync

# Activate the virtual environment to use commands directly
source .venv/bin/activate

# Now you can use openenv and python commands directly:
openenv validate
python inference.py
```

**Alternative with pip:**
```bash
pip install -e .
```

### 2. Configure Environment Variables

Create a `.env` file in the repository root or export these variables:

```bash
# Required for inference
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your-huggingface-token-here"
export IMAGE_NAME="negotiation-env:latest"
```

**Using .env file (recommended):**
```bash
# Create .env file
cat > .env << EOF
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
HF_TOKEN=your-huggingface-token-here
IMAGE_NAME=negotiation-env:latest
EOF
```

### 3. Build Docker Image

```bash
# Build the Docker image
docker build -t negotiation-env:latest .

# Verify build succeeded
docker images negotiation-env:latest
```

### 4. Run Validation

```bash
# Validate OpenEnv compliance (after activating venv)
openenv validate

# Or without activating venv
uv run openenv validate

# Run comprehensive pre-submission checks
./validate.sh
```

### 5. Run Inference

**Method 1: Using the shell script (recommended)**
```bash
# Run all 3 tasks (local testing)
./run_inference.sh

# Run a specific task (evaluator mode)
./run_inference.sh easy_conceder
./run_inference.sh medium_tft
./run_inference.sh hard_hardliner
```

**Method 2: Direct Python execution**
```bash
# After activating venv with: source .venv/bin/activate
python inference.py

# Or without activating venv
uv run python inference.py

# Run specific task
NEGOTIATION_TASK=easy_conceder python inference.py
```

Both methods automatically load environment variables from `.env` file.

### 6. Run Tests

```bash
# Using helper script
./run_tests.sh

# Or directly with pytest
uv run pytest test_env.py -v

# After activating venv
pytest test_env.py -v
```

---

## 📁 Project Structure

The project now uses a **flat structure** at the root level for OpenEnv compatibility:

```
NegotiationRL/
├── inference.py              # Main inference script (REQUIRED at root)
├── .env                      # Environment configuration
├── openenv.yaml              # OpenEnv task definitions
├── pyproject.toml            # Package metadata & dependencies
├── Dockerfile                # Container definition
├── __init__.py               # Module exports
├── client.py                 # WebSocket client
├── models.py                 # Pydantic type contracts
├── graders.py                # Grader functions for tasks
├── rewards.py                # 4 GRPO-compatible reward functions
├── strategies.py             # 5 opponent negotiation strategies
├── cli.py                    # CLI entry points
├── test_env.py               # Comprehensive test suite (25 tests)
├── server/                   # Server-side environment
│   ├── __init__.py
│   ├── app.py                # FastAPI application + main()
│   └── environment.py        # Core negotiation game logic
├── run_inference.sh          # Helper: Run inference with .env loading
├── run_tests.sh              # Helper: Run test suite
├── run_server.sh             # Helper: Start development server
├── build_docker.sh           # Helper: Build Docker image
├── validate.sh               # Helper: Pre-submission validation
├── information/              # OpenEnv educational materials
│   ├── README1-5.md          # OpenEnv philosophy & patterns
│   ├── sample_inference.py   # Inference template
│   └── *.png                 # Task requirements & criteria
└── README.md                 # This file
```

---

## 🎯 Tasks: Three Negotiation Scenarios

The environment includes three built-in negotiation tasks, defined in `openenv.yaml`:

### 1. **easy_conceder** — Establish baseline

- **Opponent**: Conceder strategy - rapidly moves toward midpoint, accepts easily
- **Difficulty**: Easy (ideal for initial training)
- **Max Rounds**: 10
- **Use case**: Verify your policy can reach agreements
- **Typical success**: 80%+ deal rate, 0.6+ utility

```python
result = env.reset(strategy_name="conceder", seed=42, max_rounds=10)
# Opponent will concede 15% per round
# Accepts any offer above BATNA
```

### 2. **medium_tft** — Learn adaptive behavior

- **Opponent**: Tit-for-Tat - mirrors your concession rate
- **Difficulty**: Medium (requires pattern recognition)
- **Max Rounds**: 10
- **Use case**: Train agents to adjust strategy based on counterpart behavior
- **Typical success**: 60%+ deal rate, 0.5+ utility

```python
result = env.reset(strategy_name="tit_for_tat", seed=42, max_rounds=10)
# If you concede 0.1 in round 1, opponent concedes ~0.09
# Must learn to signal willingness without overcommitting
```

### 3. **hard_hardliner** — Master complex negotiations

- **Opponent**: Hardliner - barely concedes (2% per round)
- **Difficulty**: Hard (requires sophisticated negotiation)
- **Max Rounds**: 15
- **Use case**: Evaluate policy robustness and deal-making skill
- **Typical success**: 30-40% deal rate, requires careful utility management

```python
result = env.reset(strategy_name="hardliner", seed=42, max_rounds=15)
# Opponent only concedes when truly necessary
# Requires finding integrative (win-win) solutions
```

### Additional Strategies

You can also use `"random"` (unpredictable offers) or `"time_pressured"` (panics near deadline) for robustness testing.

---

## 🏗️ Architecture

This project follows the **3-component OpenEnv pattern**:

### How It Works

1. **Server Side** (runs in Docker container)
   - `server/environment.py` implements the negotiation game logic
   - Maintains episode state: offers, utility calculations, deadline tracking
   - Returns typed observations (Pydantic models)
   - Computes rewards using GRPO-compatible signals

2. **Client Side** (your training code)
   - Import `NegotiationEnv` from `client.py` — it handles WebSocket communication
   - Call `reset()`, `step(action)`, and `state()`
   - No need to know about HTTP/WebSocket details
   - Works in notebooks, scripts, and TRL trainers

3. **Communication** (transparent to you)
   - WebSocket connection for efficiency
   - Type-safe JSON serialization via Pydantic
   - Automatic reconnection and error handling

```python
# Your training code doesn't care about transport
from client import NegotiationEnv
from models import NegotiationAction

env = NegotiationEnv(base_url="http://localhost:8000")
result = env.reset()           # WebSocket under the hood
result = env.step(action)      # WebSocket under the hood
state = env.state()            # WebSocket under the hood
```

---

## 🎁 Reward Functions

The environment provides **4 GRPO-compatible reward signals** designed to guide learning:

### Terminal Rewards (at episode end)

1. **deal_reward**: Did you reach a deal above your BATNA?
   - 1.0 for excellent deals (well above reservation)
   - 0.5 for breakeven deals
   - 0.0 for no deal

2. **utility_score**: How close to your ideal outcome?
   - Ratio of achieved utility to aspiration level
   - Encourages ambitious negotiation

### Shaping Rewards (every step)

3. **efficiency_reward**: Are you creating joint value?
   - Rewards moving toward Pareto frontier
   - Teaches integrative (win-win) negotiation
   - Prevents race-to-bottom

4. **concession_quality**: Are you conceding strategically?
   - Rewards conceding on low-priority issues
   - Penalizes giving up high-priority issues
   - Teaches issue prioritization

### Aggregation

The environment automatically combines these signals:

```
Non-terminal step:
  reward = 0.5 * efficiency + 0.5 * concession_quality

Terminal (deal reached):
  reward = 0.35 * deal + 0.35 * utility + 
           0.15 * efficiency + 0.15 * concession

Terminal (no deal):
  reward = 0.0 (with small shaping bonus if close to agreement)
```

This creates rich gradient information for policy gradient methods like GRPO.

---

## 🐳 Docker Commands

### Build Image

```bash
# Build from repository root
docker build -t negotiation-env:latest .

# Or use the helper script
./build_docker.sh
```

### Run Container

```bash
# Run in detached mode
docker run -d -p 8000:8000 \
  -e WORKERS=4 \
  negotiation-env:latest

# Run in foreground with logs
docker run -p 8000:8000 negotiation-env:latest

# Test the deployment
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### Stop Container

```bash
# Find container ID
docker ps

# Stop container
docker stop <container-id>

# Remove container
docker rm <container-id>
```

---

## 🧪 Development

### Run Server Locally

```bash
# Using helper script
./run_server.sh

# Or directly
uv run server

# After activating venv
server

# Server available at http://localhost:8000
# Health check: curl http://localhost:8000/health
# API docs: http://localhost:8000/docs
```

### Run Tests

```bash
# Run all tests (25 tests)
./run_tests.sh

# Or with pytest
uv run pytest test_env.py -v

# Test specific scenarios
uv run pytest test_env.py::TestStrategyBehavior -v
uv run pytest test_env.py::TestRewardBounds -v
```

### Test Coverage

The test suite covers:
- ✅ Episode completion conditions (offer accept, reject, deadline)
- ✅ All 5 strategies (hardliner, conceder, tit-for-tat, random, time-pressured)
- ✅ Reward bounds and computation
- ✅ Grader output completeness and validity
- ✅ Reproducibility via seeding
- ✅ Utility calculations (buyer/seller preferences)
- ✅ Observation structure
- ✅ HTTP endpoint integration

### Code Quality

```bash
# Type checking
mypy . --strict

# Linting
ruff check .

# Format
ruff format .
```

---

## 🚢 Deployment

### Deploy to Hugging Face Spaces

The fastest path from local code to a live endpoint:

```bash
# Push to HF Spaces (requires HF write access)
openenv push --repo-id your-username/negotiation-env
```

Your environment will be available at:
- **API Endpoint**: `https://your-username-negotiation-env.hf.space`
- **API Docs**: `https://your-username-negotiation-env.hf.space/docs`
- **Health Check**: `https://your-username-negotiation-env.hf.space/health`

Configure via Space Settings → Variables:
- `MODEL_NAME` = your LLM identifier
- `API_BASE_URL` = LLM API endpoint
- `HF_TOKEN` = your API key

### Docker Registry

Once deployed to HF Spaces, you can pull the image:

```bash
docker pull registry.hf.space/your-username/negotiation-env:latest
docker run -d -p 8000:8000 registry.hf.space/your-username/negotiation-env:latest
```

---

## 🤖 Integration with TRL/GRPO

This environment is designed for training with TRL's **GRPOTrainer**:

```python
from trl import GRPOTrainer, GRPOConfig
from client import NegotiationEnv
from models import NegotiationAction

# Custom rollout function
def rollout_func(trainer, prompts):
    """Run negotiation episodes and collect trajectories."""
    with NegotiationEnv(base_url="https://your-env.hf.space").sync() as env:
        results = []
        
        for i, prompt in enumerate(prompts):
            result = env.reset(seed=hash(prompt) % 10000)
            
            # Your LLM decides actions based on observations
            while not result.done:
                messages = [
                    {"role": "system", "content": "You are a negotiator..."},
                    {"role": "user", "content": format_state(result.observation)}
                ]
                action_text = generate(trainer, messages)
                action = parse_action(action_text)
                result = env.step(action)
            
            results.append({
                "prompt_ids": ...,
                "completion_ids": ...,
                "reward": result.reward,
            })
        
        return results

# Configure GRPO
config = GRPOConfig(
    num_train_epochs=1,
    learning_rate=5e-6,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=64,
    max_completion_length=256,
)

# Train
trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    reward_funcs=[lambda x: x["reward"]],
    rollout_func=rollout_func,
    args=config,
)
trainer.train()
```

See the [TRL documentation](https://github.com/huggingface/trl) for complete examples.

---

## 📚 OpenEnv Integration

This environment adheres strictly to the **OpenEnv specification**:

1. **Type-Safe Models**: All actions, observations, and state use Pydantic dataclasses
2. **3-Method Interface**: Every environment exposes `reset()`, `step()`, and `state()`
3. **WebSocket Transport**: Transparent to the client; use Python method calls
4. **Scalability**: Supports 100+ concurrent sessions with no shared mutable state
5. **Reproducibility**: Seeded randomness ensures deterministic episodes
6. **Docker Ready**: Runs in containers for production isolation

For more on the OpenEnv philosophy, see the `information/` folder:
- `README1.md` — Why OpenEnv (Gym → Production RL)
- `README2.md` — Using existing environments
- `README3.md` — Deploying environments
- `README4.md` — Building custom environments
- `README5.md` — Training with OpenEnv + TRL

---

## 🛠️ Helper Scripts

All scripts are located at the repo root:

| Script | Description |
|--------|-------------|
| `run_inference.sh` | Run inference (all tasks or specific task) |
| `run_tests.sh` | Run test suite (25 tests) |
| `run_server.sh` | Start local development server |
| `build_docker.sh` | Build Docker image with validation |
| `validate.sh` | Pre-submission validation (22 checks) |

**Usage:**
```bash
# Run all tasks (local testing)
./run_inference.sh

# Run specific task
./run_inference.sh easy_conceder

# Run tests
./run_tests.sh

# Start server
./run_server.sh

# Build Docker
./build_docker.sh

# Validate before submission
./validate.sh
```

---

## 🔍 Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"

**Solution:** Activate the virtual environment or use `uv run`
```bash
# Activate venv first
source .venv/bin/activate
python inference.py

# Or use uv run
uv run python inference.py
```

### "OpenAIError: The api_key client option must be set"

**Solution:** Set HF_TOKEN in `.env` file or export it
```bash
# Add to .env file
echo "HF_TOKEN=your-token-here" >> .env

# Or export directly
export HF_TOKEN=your-token-here
```

### "openenv: command not found"

**Solution:** Activate the virtual environment
```bash
source .venv/bin/activate
openenv validate

# Or use uv run
uv run openenv validate
```

### Docker build fails

**Solution:** Build from repo root (not from server/ directory)
```bash
# Correct (from repo root)
docker build -t negotiation-env:latest .

# Wrong
cd server && docker build ...
```

### Inference hangs or times out

**Solution:** Make sure Docker container is running
```bash
# Check if container is running
docker ps

# Start container if not running
docker run -d -p 8000:8000 negotiation-env:latest

# Check health
curl http://localhost:8000/health
```

---

## ✅ Pre-Submission Checklist

Before submitting to the hackathon, ensure:

- [ ] `uv sync` completes successfully
- [ ] `.env` file configured with real HF_TOKEN
- [ ] `openenv validate` passes: `[OK] Ready for multi-mode deployment`
- [ ] All 25 tests pass: `./run_tests.sh`
- [ ] All 22 validation checks pass: `./validate.sh`
- [ ] Docker builds successfully: `docker build -t negotiation-env:latest .`
- [ ] Docker container runs: `docker run -d -p 8000:8000 negotiation-env:latest`
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] Inference runs without errors: `./run_inference.sh`
- [ ] All 3 tasks produce scores in [0.0, 1.0]
- [ ] README.md has no placeholders or TODOs
- [ ] Code committed to git

**Quick validation:**
```bash
./validate.sh && echo "✅ Ready for submission!"
```

---

## 🏆 Hackathon Context

This project is a submission to the **Meta PyTorch OpenEnv Hackathon** hosted by Scaler School of Technology & Hugging Face.

**Requirements Met**:
- ✅ Custom OpenEnv-based environment
- ✅ Multi-issue negotiation domain
- ✅ 5 parameterized opponent strategies
- ✅ GRPO-compatible rewards (4 signals)
- ✅ Type-safe Pydantic models
- ✅ Docker deployment ready
- ✅ Comprehensive documentation
- ✅ Test suite with 25 tests
- ✅ HF Spaces deployment support
- ✅ Flat package structure for OpenEnv compliance
- ✅ `openenv validate` passes

---

## 📖 References

- [OpenEnv Repository](https://github.com/meta-pytorch/openenv)
- [OpenEnv Documentation](https://openenv.org)
- [TRL GRPOTrainer](https://huggingface.co/docs/trl/gpt_grpo)
- [Pydantic Models](https://docs.pydantic.dev)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)

---

## 📄 License

MIT License — See LICENSE file for full text.

---

## 💡 Support

**Questions or issues?**

1. Check `information/` folder for OpenEnv concepts
2. Review this README for setup instructions
3. Run `./validate.sh` to check your environment
4. Run `pytest test_env.py -v` to verify installation
5. Check server logs: `uv run server` shows request traces

Built with ❤️ for the Meta PyTorch OpenEnv Hackathon.
