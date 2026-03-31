# CONTRACT.md - NegotiationEnv Implementation

## Overview

Multi-issue bilateral negotiation RL environment for LLM post-training, built on OpenEnv framework. Agent negotiates with parameterized counterpart across 5 issues, learning to maximize utility while finding integrative solutions.

## Status: IMPLEMENTED

All phases completed. Ready for testing and deployment.

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `negotiation_env/__init__.py` | 21 | Module exports |
| `negotiation_env/models.py` | 230 | Pydantic models (Action, Observation, State) |
| `negotiation_env/rewards.py` | 310 | 4 pure reward functions |
| `negotiation_env/strategies.py` | 320 | 5 counterpart strategies |
| `negotiation_env/client.py` | 210 | EnvClient WebSocket implementation |
| `negotiation_env/server/__init__.py` | 5 | Server module exports |
| `negotiation_env/server/environment.py` | 480 | Core environment logic |
| `negotiation_env/server/app.py` | 18 | FastAPI application |
| `negotiation_env/server/Dockerfile` | 52 | Container definition |
| `negotiation_env/test_env.py` | 420 | Comprehensive smoke tests |
| `negotiation_env/README.md` | 340 | Documentation |
| `negotiation_env/pyproject.toml` | 65 | Package metadata |
| `negotiation_env/openenv.yaml` | 30 | OpenEnv manifest |

**Total: ~2,500 lines**

---

## API Contracts

### NegotiationAction
```python
class NegotiationAction(Action):
    action_type: Literal["offer", "accept", "reject"]
    offer: Optional[Dict[str, float]]  # Required when action_type="offer"
    message: Optional[str]
```

### NegotiationObservation (extends Observation)
```python
class NegotiationObservation(Observation):
    # Inherited: done: bool, reward: Optional[float]
    round_number: int
    rounds_remaining: int
    agent_role: Literal["buyer", "seller"]
    agent_weights: Dict[str, float]
    agent_reservation_utility: float
    agent_aspiration_utility: float
    issues: Dict[str, IssueSpec]
    agent_last_offer: Optional[Dict[str, float]]
    counterpart_last_offer: Optional[Dict[str, float]]
    counterpart_last_action: Literal["offer", "accept", "reject", "none"]
    agent_utility_if_accept: Optional[float]
    message: str
```

### NegotiationState (extends State)
```python
class NegotiationState(State):
    # Inherited: episode_id: Optional[str], step_count: int
    counterpart_strategy: str
    counterpart_weights: Dict[str, float]
    counterpart_reservation_utility: float
    counterpart_aspiration_utility: float
    offer_history: List[OfferRecord]
    deal_reached: bool
    grader: Optional[GraderOutput]
```

### GraderOutput
```python
class GraderOutput(BaseModel):
    deal_reached: bool
    agent_utility: float
    counterpart_utility: float
    joint_surplus: float
    rounds_used: int
    rounds_available: int
    strategy_detected: str
    pareto_efficiency: float
    negotiation_efficiency: float
    agent_first_offer_utility: float
    agent_final_offer_utility: float
    total_agent_concession: float
    total_counterpart_concession: float
```

---

## Reward Functions

| Function | Type | Returns |
|----------|------|---------|
| `deal_reward(deal_reached, agent_utility, agent_reservation)` | Terminal | [0, 1] |
| `utility_score(agent_utility, agent_aspiration)` | Terminal | [0, 1] |
| `efficiency_reward(current_joint, pareto_frontier, previous_joint)` | Shaping | [0, 1] |
| `concession_quality(concession_vector, weights)` | Shaping | [0, 1] |

---

## Counterpart Strategies

| Strategy | Class | Behavior |
|----------|-------|----------|
| hardliner | `HardlinerStrategy` | 2% concession/round, 85% aspiration threshold |
| conceder | `ConcederStrategy` | 15% concession/round, accepts at BATNA |
| tit_for_tat | `TitForTatStrategy` | 90% mirror factor, min 1% concession |
| random | `RandomStrategy` | Beta-distributed random offers |
| time_pressured | `TimePressuredStrategy` | 2% early, 25% after panic threshold |

---

## Verification Commands

```bash
# Install dependencies
cd negotiation_env
uv sync

# Run tests
uv run pytest test_env.py -v

# Run server locally
uv run server

# Deploy to HF Spaces
openenv push --repo-id <username>/negotiation-env
```

---

## Implementation Notes

1. **Concurrency**: `SUPPORTS_CONCURRENT_SESSIONS = True` with no shared mutable state
2. **Reproducibility**: All randomness seeded via `seed` parameter
3. **GRPO Compatibility**: Rewards in [0, 1], shaping rewards every step
4. **Type Safety**: Full Pydantic validation, mypy-compatible
5. **No ML Dependencies**: Server-side is lightweight (no torch/transformers)

---

## Open Items

- [ ] Integration testing with actual OpenEnv client
- [ ] Performance benchmarking with 100+ concurrent sessions
- [ ] HF Spaces deployment verification
- [ ] TRL GRPOTrainer integration testing
