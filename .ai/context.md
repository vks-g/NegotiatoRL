# Agent Skill: Negotiation Environment (OpenEnv Hackathon)

## Purpose

This skill enables the agent to design, implement, test, and deploy a negotiation-based reinforcement learning environment using OpenEnv.

The environment simulates multi-round negotiations under:

- Partial observability
- Strategic opponent behavior
- Deadline constraints

This follows the RL loop:

```
observe → act → reward → repeat
```

## Objective

Build a production-ready environment:

> "A multi-round negotiation simulation environment for training and evaluating decision-making agents under uncertainty and strategic interaction."

The environment must:

- Implement `reset()`, `step()`, `state()`
- Include 3 difficulty tasks
- Include reward shaping (not sparse)
- Include grading functions
- Include a baseline agent
- Be deployable via OpenEnv

## Architecture (STRICT)

```
app/
  env.py
  models.py
  opponent.py
  reward.py
  tasks.py
  graders.py

main.py
openenv.yaml
inference.py
Dockerfile
```

## Environment Design

### Action

```json
{
  "offer": float,
  "message": str,
  "accept": bool
}
```

### Observation

```json
{
  "round": int,
  "agent_offer": float,
  "opponent_offer": float,
  "history": list,
  "deadline": int,
  "agreement_reached": bool
}
```

### Hidden State (NOT exposed)

- `opponent_min_price`
- `opponent_personality`
- `internal negotiation strategy`

## Opponent System

**Implement in:** `opponent.py`

### Personalities

#### Aggressive
- Starts high
- Slow concessions
- Accepts only near max value

#### Lenient
- Concedes quickly
- Accepts early
- Low resistance

#### Strategic
- Moves toward midpoint
- Adapts to agent behavior
- Becomes flexible near deadline

### Behavior Rules

- Concession increases as deadline approaches
- Negotiation trajectory must be deterministic + logical, not random
- Opponent must react to agent's previous moves

## Reward Design (CRITICAL)

**Implement in:** `reward.py`

### Required Components

1. **Step Penalty**
   - Small negative reward each step
   - Encourages faster deals

2. **Improvement Reward**
   - Reward when agent improves offer toward agreement
   - Penalize worsening offers

3. **Final Reward**
   - Triggered on termination
   - Based on:
     - Profit
     - Fairness
     - Efficiency

### Example Structure

```
reward =
    step_penalty
  + improvement_bonus
  + final_reward (if done)
```

## Tasks (MANDATORY)

**Implement in:** `tasks.py`

### Easy
- Lenient opponent
- Wide acceptable range
- Simple success/fail scoring

### Medium
- Moderate opponent
- Tighter margins
- Score based on profit

### Hard
- Aggressive opponent
- Strict deadline
- Scoring based on:
  - Deal quality
  - Speed
  - Fairness

## Graders (MANDATORY)

**Implement in:** `graders.py`

Each task must return:

- `score ∈ [0, 1]`

### Scoring Dimensions

- Success (deal reached)
- Efficiency (steps used)
- Deal quality (distance from optimal outcome)
- Fairness (optional but high value)

## Environment Logic

**Implement in:** `env.py`

### reset()

Initialize:
- Hidden opponent parameters
- `round = 0`
- `history = []`
- `deadline`
- Return initial observation

### step(action)

Process agent action:
1. Validate input
2. Generate opponent response
3. Update negotiation state
4. Compute reward
5. Append to history
6. Check termination:
   - Agreement reached
   - Agent accepts
   - Deadline reached

### state()

Return internal metadata:
- `episode_id`
- `step_count`
- `hidden configs` (optional for debugging)

## Baseline Agent (REQUIRED)

**Implement in:** `inference.py`

### Strategy

- Move offer toward midpoint between agent and opponent
- Gradually concede
- Accept when:
  - Within acceptable threshold
  - Near deadline

### Purpose

- Ensures reproducibility
- Used for evaluation sanity checks
- Must consistently produce non-random behavior

## API Requirements

Expose via FastAPI:

- `/reset`
- `/step`
- `/state`
- `/health`

Must support:

- Concurrent sessions
- WebSocket (preferred via OpenEnv)

## Deployment

### Local

```bash
uv run server
```

### Docker

```bash
docker build -t negotiation-env .
docker run -p 8000:8000 negotiation-env
```

### OpenEnv

```bash
openenv push --repo-id <username>/negotiation-env
```

## Failure Conditions

You will fail validation if:

Missing any of:
- Tasks
- Graders
- `inference.py`

Reward is:
- Constant
- Trivial
- Only final reward

Environment does not:
- Respond to `/reset` or `/step`
- Maintain state properly

## 🏆 Evaluation Strategy

Optimize for:

- Real-world relevance
- Structured RL design
- Clarity of environment API
- Meaningful reward shaping

## Key Insight

This is not a game.

This is a decision-making simulation under uncertainty, aligned with real-world negotiation dynamics.

Strong implementations:

- Model opponent psychology
- Balance fairness vs profit
- Reward trajectory, not just outcome

## Agent Execution Plan

1. Define schemas (`models.py`)
2. Implement environment loop (`env.py`)
3. Build opponent strategies (`opponent.py`)
4. Design reward shaping (`reward.py`)
5. Implement tasks (`tasks.py`)
6. Implement graders (`graders.py`)
7. Create baseline agent (`inference.py`)
8. Test locally
9. Deploy via OpenEnv

## Final Goal

A clean, testable, deployable RL environment that:

- Supports training
- Supports evaluation
- Demonstrates strategic negotiation behavior
