# NegotiationEnv: Multi-Issue Bilateral Negotiation RL Environment

A production-grade reinforcement learning environment for training LLMs on multi-issue bilateral negotiations, built on the [OpenEnv](https://github.com/meta-pytorch/openenv) framework.

## Overview

NegotiationEnv simulates realistic negotiations between an LLM agent and a parameterized counterpart. The agent must learn to:
- Make strategic offers across multiple issues
- Recognize and adapt to different opponent strategies
- Find integrative solutions (win-win) while maximizing own utility
- Handle time pressure and imperfect information

### Key Features

- **5 Negotiation Issues**: Price, Quantity, Delivery, Warranty, Payment Terms
- **5 Opponent Strategies**: Hardliner, Conceder, Tit-for-Tat, Random, Time-Pressured
- **4 GRPO-Compatible Rewards**: Rich gradient signal for policy optimization
- **Comprehensive Grader**: Structured evaluation for hackathon LLM scoring
- **Reproducible**: Seeded randomness for deterministic episodes
- **Concurrent**: Supports 100+ simultaneous WebSocket sessions

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/negotiation-env
cd negotiation-env

# Install dependencies
pip install -e .

# Or with uv
uv sync
```

## Quick Start

### Run the Server Locally

```bash
# With uv
cd negotiation_env
uv run server

# Or with uvicorn directly
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

### Connect as a Client

```python
from negotiation_env import NegotiationEnv, NegotiationAction

# Sync usage (for notebooks/scripts)
with NegotiationEnv(base_url="http://localhost:8000").sync() as env:
    result = env.reset(seed=42, strategy_name="conceder")
    
    while not result.done:
        # Make an offer
        action = NegotiationAction(
            action_type="offer",
            offer={
                "price": 0.3,        # Low price (good for buyer)
                "quantity": 0.8,     # High quantity
                "delivery_days": 0.2, # Fast delivery
                "warranty_months": 0.9, # Long warranty
                "payment_terms": 0.7,  # Delayed payment
            }
        )
        result = env.step(action)
        
        print(f"Round {result.observation.round_number}")
        print(f"  Counterpart offered: {result.observation.counterpart_last_offer}")
        print(f"  Your utility if accept: {result.observation.agent_utility_if_accept}")
        
        # Accept if good enough
        if result.observation.agent_utility_if_accept > 0.6:
            action = NegotiationAction(action_type="accept")
            result = env.step(action)
    
    print(f"Final reward: {result.reward}")
    print(f"Deal reached: {env.state().deal_reached}")
```

## Environment Specification

### Action Space

| Action Type | Description | Required Fields |
|-------------|-------------|-----------------|
| `offer` | Make an offer on all issues | `offer: Dict[str, float]` |
| `accept` | Accept counterpart's last offer | - |
| `reject` | Walk away (ends negotiation) | - |

```python
# Make an offer
action = NegotiationAction(
    action_type="offer",
    offer={
        "price": 0.3,           # 0=lowest, 1=highest
        "quantity": 0.8,        # 0=1 unit, 1=10 units
        "delivery_days": 0.2,   # 0=1 day, 1=60 days
        "warranty_months": 0.9, # 0=none, 1=36 months
        "payment_terms": 0.7,   # 0=upfront, 1=installments
    }
)

# Accept counterpart's offer
action = NegotiationAction(action_type="accept")

# Reject and walk away
action = NegotiationAction(action_type="reject", message="Too expensive")
```

### Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `round_number` | int | Current round (1-indexed) |
| `rounds_remaining` | int | Rounds until deadline |
| `agent_role` | str | "buyer" or "seller" |
| `agent_weights` | Dict[str, float] | Issue importance weights |
| `agent_reservation_utility` | float | BATNA threshold |
| `agent_aspiration_utility` | float | Ideal utility target |
| `counterpart_last_offer` | Dict[str, float] | Their most recent offer |
| `counterpart_last_action` | str | "offer", "accept", "reject", "none" |
| `agent_utility_if_accept` | float | Your utility if you accept |
| `done` | bool | Episode complete? |
| `reward` | float | Step reward [0, 1] |

### Issue Space

| Issue | Agent Preference | Value Mapping |
|-------|------------------|---------------|
| **price** | Buyer: low, Seller: high | 0.0 = $100, 1.0 = $1000 |
| **quantity** | Buyer: high, Seller: low | 0.1 = 1 unit, 1.0 = 10 units |
| **delivery_days** | Buyer: low (fast), Seller: high (slow) | 0 = 1 day, 1 = 60 days |
| **warranty_months** | Buyer: high (long), Seller: low (short) | 0 = none, 1 = 36 months |
| **payment_terms** | Buyer: high (delayed), Seller: low (upfront) | 0 = upfront, 1 = installments |

### Counterpart Strategies

| Strategy | Behavior | Difficulty |
|----------|----------|------------|
| **hardliner** | Barely concedes, demands near-aspiration | Hard |
| **conceder** | Rapidly moves to midpoint, accepts easily | Easy |
| **tit_for_tat** | Mirrors agent's concession rate | Medium |
| **random** | Uniform random offers | Unpredictable |
| **time_pressured** | Small early concessions, panics at deadline | Medium-Hard |

## Reward Functions

NegotiationEnv provides 4 reward signals optimized for GRPO training:

### Terminal Rewards (Episode End)

1. **deal_reward**: Did you reach a deal above BATNA?
   - 1.0 for excellent deals (well above reservation)
   - 0.5 for BATNA-level deals
   - 0.0 for no deal

2. **utility_score**: How good was the deal vs your aspiration?
   - Ratio of achieved utility to aspiration level

### Shaping Rewards (Every Step)

3. **efficiency_reward**: Are you creating joint value?
   - Rewards moving toward Pareto frontier
   - Teaches win-win negotiation

4. **concession_quality**: Are you conceding strategically?
   - Rewards conceding on low-priority issues
   - Penalizes giving up high-priority issues

### Reward Aggregation

```
Non-terminal: 0.5 * efficiency + 0.5 * concession_quality
Terminal (deal): 0.35 * deal + 0.35 * utility + 0.15 * efficiency + 0.15 * concession
Terminal (no deal): 0.0 (with small shaping signal)
```

## Grader Output

After each episode, the `/state` endpoint returns comprehensive evaluation:

```python
state = env.state()
grader = state.grader

print(f"Deal reached: {grader.deal_reached}")
print(f"Agent utility: {grader.agent_utility:.3f}")
print(f"Joint surplus: {grader.joint_surplus:.3f}")
print(f"Pareto efficiency: {grader.pareto_efficiency:.3f}")
print(f"Strategy: {grader.strategy_detected}")
print(f"Rounds used: {grader.rounds_used}/{grader.rounds_available}")
```

## Training with TRL GRPOTrainer

Example integration with TRL for GRPO training:

```python
from trl import GRPOTrainer, GRPOConfig
from negotiation_env import NegotiationEnv, NegotiationAction

def rollout_func(trainer, prompts):
    """Custom rollout function for negotiation."""
    with NegotiationEnv(base_url="https://your-space.hf.space").sync() as env:
        results = []
        
        for prompt in prompts:
            result = env.reset(seed=hash(prompt) % 10000)
            
            # Run negotiation episode
            history = []
            while not result.done:
                # Generate action from model
                messages = format_negotiation_prompt(result.observation, history)
                completion = generate_completion(trainer, messages)
                
                # Parse and execute action
                action = parse_action(completion)
                result = env.step(action)
                history.append((action, result))
            
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
    num_generations=2,
    max_completion_length=128,
    use_vllm=True,
)

trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-1.5B-Instruct",
    reward_funcs=[lambda x: x["reward"]],
    rollout_func=rollout_func,
    args=config,
)

trainer.train()
```

## Deployment

### Deploy to Hugging Face Spaces

```bash
cd negotiation_env
openenv push --repo-id your-username/negotiation-env
```

Your environment will be available at:
- **API**: `https://your-username-negotiation-env.hf.space`
- **Docs**: `https://your-username-negotiation-env.hf.space/docs`
- **Health**: `https://your-username-negotiation-env.hf.space/health`

### Docker Deployment

```bash
# Build
docker build -t negotiation-env:latest -f server/Dockerfile .

# Run
docker run -d -p 8000:8000 negotiation-env:latest

# With configuration
docker run -d -p 8000:8000 \
    -e WORKERS=4 \
    -e MAX_CONCURRENT_ENVS=100 \
    negotiation-env:latest
```

## Testing

```bash
# Run smoke tests
cd negotiation_env
pytest test_env.py -v

# Or with uv
uv run pytest test_env.py -v
```

## Project Structure

```
negotiation_env/
├── __init__.py              # Module exports
├── models.py                # Pydantic models (Action, Observation, State)
├── client.py                # WebSocket client (NegotiationEnv)
├── rewards.py               # Pure reward functions
├── strategies.py            # 5 counterpart strategies
├── test_env.py              # Smoke tests
├── openenv.yaml             # OpenEnv manifest
├── pyproject.toml           # Package metadata
└── server/
    ├── __init__.py
    ├── environment.py       # Core environment logic
    ├── app.py               # FastAPI application
    └── Dockerfile           # Container definition
```

## API Reference

### Environment Methods

| Method | Description |
|--------|-------------|
| `reset(seed, episode_id, max_rounds, strategy_name, agent_role)` | Start new episode |
| `step(action)` | Take action, get observation |
| `state` | Get full state including grader |

### Reset Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seed` | int | None | Random seed for reproducibility |
| `episode_id` | str | UUID | Custom episode identifier |
| `max_rounds` | int | 10 | Deadline rounds |
| `strategy_name` | str | random | Force specific strategy |
| `agent_role` | str | random | Force "buyer" or "seller" |

## License

MIT License - see LICENSE file.

## Acknowledgments

Built for the Meta PyTorch OpenEnv Hackathon hosted by Scaler School of Technology & Hugging Face.
