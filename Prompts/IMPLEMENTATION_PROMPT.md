# Implementation Prompt: Optimize `inference.py` for Negotiation RL Agent

> **Target file:** `inference.py` (the only file to modify)
> **Goal:** Improve the LLM negotiation agent's scores from ~0.55 average to ~0.84 average across easy/medium/hard opponent strategies.

---

## Problem Diagnosis

The original `inference.py` has these issues causing low scores on medium (Tit-for-Tat) and hard (Hardliner) tasks:

1. **Offer oscillation** — The LLM retracts offers between rounds (e.g., price goes 0.20 → 0.15 → 0.18). Against Tit-for-Tat opponents, retractions signal zero concession, so the opponent mirrors stubbornness and no deal is reached.
2. **Premature acceptance of bad deals** — The agent panics near the deadline and accepts whatever the counterpart offers, even if utility is below reservation.
3. **Generic system prompt** — The prompt says "concede on low-priority issues" but gives no concrete guidance. The LLM ignores issue weights entirely (e.g., holds price at 0.05 for 10 rounds despite price having weight=0.01).
4. **Uniform concessions** — When the LLM does concede, it concedes equally on all issues instead of giving more on low-weight (cheap) issues and less on high-weight (expensive) issues.
5. **Fragile JSON parsing** — Some models output reasoning text before JSON; the parser fails and the static fallback offer gets stuck repeating.
6. **High temperature (0.7)** — Causes erratic, inconsistent offers.

---

## Changes to Implement

Apply all of the following changes to `inference.py`. Do NOT modify any other file. Do NOT change the logging format, task configurations, or the `main()` function.

### 1. Lower Temperature

Change `TEMPERATURE` from `0.7` to `0.3`. This produces more consistent, predictable offers from the LLM.

### 2. Replace the System Prompt

Replace the existing `SYSTEM_PROMPT` with one that has these characteristics:
- Lists all 5 issues and role-based preferences (buyer vs seller)
- Shows only two actions: `offer` and `accept` (remove `reject` — a bad deal always beats no deal)
- Has explicit **CRITICAL RULES**:
  - **Never retract** — every offer must concede from the previous one, never go backwards on any issue
  - **Weight-based concession sizing** — LOW-weight issues (< 0.15): concede 0.10–0.15 per round; MEDIUM-weight (0.15–0.30): concede 0.05–0.08; HIGH-weight (> 0.30): concede only 0.01–0.03
  - **When to accept** — only when the observation explicitly says "Accepting is good" or "accepting is reasonable" (the code will compute this)
  - **Opening offer** — Round 1 should be at ideal extremes (buyer: price=0.05, quantity=0.95, etc.)
  - **Minimum concession pace** — must move at least 0.05 total utility per round; increase pace in final 30% of rounds
  - **Never reject** — explicitly ban the reject action
- End with "Respond with valid JSON only."

### 3. Rewrite `format_observation()` to Accept Rich History

Change the signature to `format_observation(obs, offer_history: List[Dict[str, Any]])`.

The new observation format should include:
- **Round counter** with remaining rounds
- **Issue weights sorted by priority** (highest first) with numeric values
- **Reservation, aspiration, and accept threshold** (threshold = reservation + 0.3 × (aspiration − reservation))
- **Last offers from both sides** with utility values
- **Accept guidance** — a computed string:
  - If final round and utility ≥ reservation: "FINAL ROUND: accepting is reasonable."
  - If utility ≥ accept_threshold: "Above your accept threshold. Accepting is good."
  - Else: "Below accept threshold by X. Keep negotiating."
- **Per-issue concession recommendations** — for each issue (sorted by weight ascending), compute a recommended target value based on:
  - Weight ratio relative to max weight determines the concession size:
    - `w/max_w < 0.3` (LOW-COST): `step_size = min(0.15 × pace, gap × 0.4)`
    - `w/max_w < 0.6` (MEDIUM): `step_size = min(0.07 × pace, gap × 0.2)`
    - else (HIGH-VALUE): `step_size = min(0.02 × pace, gap × 0.1)`
  - `pace = 1.5` if in final 30% of rounds, else `1.0`
  - Direction depends on role (buyer raises price, lowers quantity, etc.)
  - Format each as: `issue (w=X.XX, LABEL): current -> target`
- **Negotiation history analysis**:
  - Agent utility trend (last two values)
  - Best utility achieved so far
  - Counterpart's offer utilities over time with trend analysis
  - Labels: "STUBBORN" if counterpart movement < 0.02/round, "CONCEDING" if > 0.05/round

### 4. Improve `parse_llm_response()` to Handle Reasoning Models

Change return type to `Optional[NegotiationAction]` (return `None` on failure instead of a static fallback).

After trying direct JSON parse and markdown code block extraction, add a fallback:
- Use regex `r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'` to find all JSON-like blocks in the text
- Iterate in reverse (last JSON block is usually the answer)
- Accept any parsed block that contains `"action_type"` or `"offer"` key
- As a last resort, check if the text contains `"accept"` and return an accept action
- Return `None` if nothing works

### 5. Add `enforce_monotonic_concession()` Function

New function with signature:
```python
def enforce_monotonic_concession(
    new_offer: Dict[str, float],
    last_offer: Optional[Dict[str, float]],
    role: str,
    weights: Optional[Dict[str, float]] = None,
    ensure_progress: bool = True,
) -> Dict[str, float]:
```

Logic:
- Define buyer concession directions: price=+1, quantity=-1, delivery_days=+1, warranty_months=-1, payment_terms=-1 (seller is the opposite)
- For each issue: if the delta from last_offer goes AGAINST the concession direction, clamp it back to last_offer's value
- If `ensure_progress=True` and the resulting offer equals last_offer exactly (no movement), nudge the 3 lowest-weight issues by 0.03 in the concession direction

### 6. Add `should_accept_heuristic()` Function

```python
def should_accept_heuristic(obs) -> bool:
```

- Return `False` if `agent_utility_if_accept` is None
- Final round (`rounds_remaining <= 1`): accept if utility ≥ reservation
- Otherwise: accept if utility ≥ `reservation + 0.3 × (aspiration - reservation)`

### 7. Rewrite `get_model_action()`

Change signature to accept `offer_history: List[Dict[str, Any]]` instead of `history: List[str]`.

Flow (in order):
1. **Pre-LLM accept check**: call `should_accept_heuristic(obs)`. If True, return accept immediately without calling the LLM.
2. **Deadline panic**: if `rounds_remaining <= 1` and both parties have offers, compute a big concession offer (move 15–50% toward counterpart, scaled by weight — low-weight issues move 50%, high-weight move 15%). Return this directly without calling the LLM.
3. **Call the LLM** with `format_observation(obs, offer_history)`. If `parse_llm_response` returns `None`, use `_make_concession_offer(obs)` as fallback. If the API call throws an exception, also use the fallback.
4. **Post-LLM guards**:
   - If action is `accept`: verify utility ≥ reservation. If not, override with `_make_concession_offer(obs)`.
   - If action is `reject`: override with `_make_concession_offer(obs)`.
   - If action is `offer`: pass through `enforce_monotonic_concession()` with `weights=obs.agent_weights`.

### 8. Add `_make_concession_offer()` Function

Weight-aware dynamic fallback:
- If both `agent_last_offer` and `counterpart_last_offer` exist: for each issue, move toward counterpart by a weight-scaled factor: `factor = 0.05 + 0.25 × (1.0 - w/max_weight)`. Low-weight issues get factor ~0.30, high-weight get ~0.05.
- If no prior offers (first round): return an aggressive opening based on role (buyer: price=0.10, quantity=0.90, delivery=0.10, warranty=0.90, payment=0.80; seller: opposite).

### 9. Update `run_task()` History Tracking

Replace `history: List[str]` with `offer_history: List[Dict[str, Any]]`.

After each step, build a history entry dict with:
```python
{
    "step": step,
    "action": action_str,
    "reward": reward,
    "agent_utility": new_obs.agent_utility_of_last_offer,
    "cp_utility_of_agent_offer": None,
    "cp_offer_utility_for_agent": new_obs.agent_utility_if_accept,
}
```

Pass `offer_history` (not `history`) to `get_model_action()`.

---

## Expected Results

| Task | Original Score | After Changes |
|------|---------------|---------------|
| easy_conceder | 0.87 | 0.88 |
| medium_tft | 0.40 | 0.85 |
| hard_hardliner | 0.38 | 0.79 |
| **Average** | **0.55** | **0.84** |

---

## What NOT to Change

- Do not modify any other file (environment, rewards, strategies, models, client)
- Do not change the logging format (`[START]`, `[STEP]`, `[END]` lines)
- Do not change task configurations (names, strategies, seeds, max_rounds)
- Do not change the `main()` function
- Do not change the score calculation (`rewards[-1]`)
