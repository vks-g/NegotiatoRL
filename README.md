# NegotiationRL

A production-grade **multi-issue bilateral negotiation RL environment** for training LLMs on complex negotiation tasks. Built on the [OpenEnv](https://github.com/meta-pytorch/openenv) framework for OpenAI Gym-like simplicity with Docker-based isolation, WebSocket APIs, and native TRL/GRPO integration.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/negotiatorl/NegotiationRL
cd NegotiationRL

# Install with uv (recommended)
cd negotiation_env
uv sync

# Or with pip
pip install -e .
```

### Run the Server Locally

```bash
# Terminal 1: Start the environment server
cd negotiation_env
uv run server
# Server available at http://localhost:8000

# Health check
curl http://localhost:8000/health
```

### Test with a Simple Agent

```bash
# Terminal 2: Run a quick test
cd negotiation_env
uv run pytest test_env.py -v

# Or write your own client
python -c "
from negotiation_env import NegotiationEnv, NegotiationAction

with NegotiationEnv(base_url='http://localhost:8000').sync() as env:
    result = env.reset(seed=42)
    print(f'Negotiating against: {result.observation.agent_role}')
    print(f'Your utility if accept: {result.observation.agent_utility_if_accept}')
"
```

## Architecture

This project follows the **3-component OpenEnv pattern**:

```
negotiation_env/
├── models.py                # Type-safe contracts (Action, Observation, State)
├── client.py                # Python client (what you import in training code)
├── rewards.py               # Pure reward functions (4 signals)
├── strategies.py            # 5 parameterized opponent strategies
├── server/
│   ├── environment.py       # Core negotiation logic (reset, step, state)
│   ├── app.py               # FastAPI + WebSocket server
│   └── Dockerfile           # Containerized for reproducibility
├── openenv.yaml             # OpenEnv manifest
├── pyproject.toml           # Package metadata
├── test_env.py              # Smoke tests
└── README.md                # Detailed environment docs
```

### How It Works

1. **Server Side** (runs in Docker container)
   - `environment.py` implements the negotiation game logic
   - Maintains episode state: offers, utility calculations, deadline tracking
   - Returns typed observations (Pydantic models)
   - Computes rewards using GRPO-compatible signals

2. **Client Side** (your training code)
   - Import `NegotiationEnv` — it handles WebSocket communication
   - Call `reset()`, `step(action)`, and `state()`
   - No need to know about HTTP/WebSocket details
   - Works in notebooks, scripts, and TRL trainers

3. **Communication** (transparent to you)
   - WebSocket connection for efficiency
   - Type-safe JSON serialization via Pydantic
   - Automatic reconnection and error handling

```python
# Your training code doesn't care about transport
env = NegotiationEnv(base_url="http://localhost:8000")
result = env.reset()           # WebSocket under the hood
result = env.step(action)      # WebSocket under the hood
state = env.state()            # WebSocket under the hood
```

## Tasks: Three Negotiation Scenarios

The environment includes three built-in negotiation tasks, defined in `openenv.yaml`:

### 1. **easy_conceder** — Establish baseline

- **Opponent**: Rapidly moves toward midpoint, accepts easily
- **Difficulty**: Easy (ideal for initial training)
- **Use case**: Verify your policy can reach agreements
- **Typical success**: 80%+ deal rate, 0.6+ utility

```python
result = env.reset(strategy_name="conceder")
# Opponent will concede 15% per round
# Accepts any offer above BATNA
```

### 2. **medium_tit_for_tat** — Learn adaptive behavior

- **Opponent**: Mirrors your concession rate (min 1%)
- **Difficulty**: Medium (requires pattern recognition)
- **Use case**: Train agents to adjust strategy based on counterpart behavior
- **Typical success**: 60%+ deal rate, 0.5+ utility

```python
result = env.reset(strategy_name="tit_for_tat")
# If you concede 0.1 in round 1, opponent concedes ~0.09
# Must learn to signal willingness without overcommitting
```

### 3. **hard_hardliner** — Master complex negotiations

- **Opponent**: Barely concedes (2% per round), demands near-aspiration
- **Difficulty**: Hard (requires sophisticated negotiation)
- **Use case**: Evaluate policy robustness and deal-making skill
- **Typical success**: 30-40% deal rate, requires careful utility management

```python
result = env.reset(strategy_name="hardliner")
# Opponent only concedes when truly necessary
# Requires finding integrative (win-win) solutions
```

### Additional Strategies

You can also use `"random"` (unpredictable offers) or `"time_pressured"` (panics near deadline) for robustness testing.

## Configuration

### Environment Variables

Set these before running `docker run` or deploying to Hugging Face Spaces:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8000` | Server endpoint for inference |
| `MODEL_NAME` | `Qwen/Qwen2.5-72B-Instruct` | LLM identifier for inference |
| `HF_TOKEN` | (required) | Hugging Face API key for model access |
| `LOCAL_IMAGE_NAME` | `negotiation-env:latest` | Docker image name if using local container |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `WORKERS` | `4` | Uvicorn worker processes |
| `MAX_CONCURRENT_SESSIONS` | `100` | Max concurrent WebSocket connections |

### Reset Parameters

When calling `env.reset()`, you can customize the negotiation:

```python
result = env.reset(
    seed=42,                      # For reproducibility
    episode_id="ep-001",          # Custom ID (auto-generated if omitted)
    strategy_name="hardliner",    # Force specific opponent
    agent_role="buyer",           # Force "buyer" or "seller"
    max_rounds=15                 # Override default 10 rounds
)
```

## Reward Functions

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

## Development

### Run Tests Locally

```bash
cd negotiation_env

# Run all smoke tests
uv run test

# Or with pytest directly
pytest test_env.py -v

# Test specific scenarios
pytest test_env.py::test_hardliner_negotiation -v
pytest test_env.py::test_concurrent_sessions -v
```

### Tests Cover

- ✅ All 5 strategies (hardliner, conceder, tit-for-tat, random, time-pressured)
- ✅ Valid action validation
- ✅ Utility calculations
- ✅ Reward computation
- ✅ Concurrent WebSocket sessions (100+)
- ✅ Reproducibility via seeding
- ✅ Grader output accuracy

### Code Quality

```bash
# Type checking
mypy negotiation_env --strict

# Linting
ruff check negotiation_env

# Format
ruff format negotiation_env
```

## Deployment

### Deploy to Hugging Face Spaces

The fastest path from local code to a live endpoint:

```bash
cd negotiation_env

# Push to HF Spaces (you'll need write access to your HF account)
openenv push --repo-id negotiatorl/negotiation-env
```

Your environment will be available at:
- **API Endpoint**: `https://negotiatorl-negotiation-env.hf.space`
- **API Docs**: `https://negotiatorl-negotiation-env.hf.space/docs`
- **Health Check**: `https://negotiatorl-negotiation-env.hf.space/health`

Configure via Space Settings → Variables:
- `MODEL_NAME` = your LLM identifier
- `API_BASE_URL` = LLM API endpoint
- `HF_TOKEN` = your API key

### Docker Build & Run Locally

```bash
# Build the image
docker build -t negotiation-env:latest -f negotiation_env/server/Dockerfile .

# Run the container
docker run -d -p 8000:8000 \
  -e WORKERS=4 \
  -e MAX_CONCURRENT_ENVS=100 \
  negotiation-env:latest

# Test the deployment
curl http://localhost:8000/health
# {"status": "healthy"}
```

### Docker Registry

Once deployed to HF Spaces, you can pull the image:

```bash
docker pull registry.hf.space/negotiatorl/negotiation-env:latest
docker run -d -p 8000:8000 registry.hf.space/negotiatorl/negotiation-env:latest
```

## Integration with OpenEnv + TRL

This environment is designed for training with TRL's **GRPOTrainer**:

```python
from trl import GRPOTrainer, GRPOConfig
from negotiation_env import NegotiationEnv, NegotiationAction

# Custom rollout function
def rollout_func(trainer, prompts):
    """Run negotiation episodes and collect trajectories."""
    with NegotiationEnv(base_url="https://negotiatorl-negotiation-env.hf.space").sync() as env:
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
    use_vllm=True,
    vllm_mode="colocate",
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

## OpenEnv Integration

This environment adheres strictly to the **OpenEnv specification**:

1. **Type-Safe Models**: All actions, observations, and state use Pydantic dataclasses
2. **3-Method Interface**: Every environment exposes `reset()`, `step()`, and `state()`
3. **WebSocket Transport**: Transparent to the client; use Python method calls
4. **Scalability**: Supports 100+ concurrent sessions with no shared mutable state
5. **Reproducibility**: Seeded randomness ensures deterministic episodes
6. **Docker Ready**: Runs in containers for production isolation

For more on the OpenEnv philosophy, see the included `Information/` folder:
- `README1.md` — Why OpenEnv (Gym → Production RL)
- `README2.md` — Using existing environments
- `README3.md` — Deploying environments
- `README4.md` — Building custom environments
- `README5.md` — Training with OpenEnv + TRL

## Project Structure

```
NegotiationRL/
├── negotiation_env/
│   ├── __init__.py              # Module exports
│   ├── models.py                # Pydantic contracts (252 lines)
│   ├── client.py                # WebSocket client
│   ├── rewards.py               # 4 reward functions (pure)
│   ├── strategies.py            # 5 opponent strategies
│   ├── test_env.py              # Comprehensive tests
│   ├── openenv.yaml             # OpenEnv manifest
│   ├── pyproject.toml           # Package metadata
│   ├── README.md                # Detailed environment docs
│   └── server/
│       ├── __init__.py
│       ├── environment.py       # Core negotiation engine
│       ├── app.py               # FastAPI server
│       └── Dockerfile           # Container definition
├── Information/                 # OpenEnv educational materials
│   ├── README1-5.md             # OpenEnv philosophy & patterns
│   ├── sample_inference.py      # Inference script template
│   ├── Detailed_Requirements.png
│   ├── Evaluation_Criteria.png
│   └── ... (task images, validation scripts)
├── .ai-workflow/                # Development contracts & logs
│   └── contracts/
│       └── negotiation-env-contract.md
├── README.md                    # This file
└── .gitignore
```

## Hackathon Context

This project is a submission to the **Meta PyTorch OpenEnv Hackathon** hosted by Scaler School of Technology & Hugging Face.

**Requirements Met**:
- ✅ Custom OpenEnv-based environment
- ✅ Multi-issue negotiation domain
- ✅ 5 parameterized opponent strategies
- ✅ GRPO-compatible rewards (4 signals)
- ✅ Type-safe Pydantic models
- ✅ Docker deployment ready
- ✅ Comprehensive documentation
- ✅ Test suite with smoke tests
- ✅ HF Spaces deployment support

**Submission Checklist**:
- ✅ `README.md` (this file, in repo root)
- ✅ `negotiation_env/README.md` (detailed environment docs)
- ✅ All source code in `negotiation_env/`
- ✅ Tests in `negotiation_env/test_env.py`
- ✅ Docker build works
- ✅ OpenEnv client interface confirmed
- ✅ No hardcoded secrets
- ✅ Python 3.11+ compatible

## References

- [OpenEnv Repository](https://github.com/meta-pytorch/openenv)
- [OpenEnv Documentation](https://openenv.org)
- [TRL GRPOTrainer](https://huggingface.co/docs/trl/gpt_grpo)
- [Pydantic Models](https://docs.pydantic.dev)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)

## License

MIT License — See LICENSE file for full text.

---

**Questions or issues?**

1. Check `negotiation_env/README.md` for detailed environment reference
2. Review `Information/` folder for OpenEnv concepts
3. Run `pytest test_env.py -v` to verify setup
4. Check server logs: `uv run server` shows request traces

Built with ❤️ for the OpenEnv Hackathon.
