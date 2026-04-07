"""
Inference Script for NegotiationEnv
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
    IMAGE_NAME     The name of the local Docker image for the environment.

- Defaults are set for API_BASE_URL and MODEL_NAME:
    API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after env.close(), always emitted (even on exception).
    - reward and rewards are formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw last_action_error string, or null if none.
    - All fields on a single line with no newlines within a line.
    - Each tasks should return score in [0, 1]

  Example:
    [START] task=easy_conceder env=negotiation_env model=Qwen/Qwen2.5-72B-Instruct
    [STEP] step=1 action=offer(price=0.3,quantity=0.8,...) reward=0.45 done=false error=null
    [STEP] step=2 action=accept() reward=0.78 done=true error=null
    [END] success=true steps=2 score=0.78 rewards=0.45,0.78
"""

import asyncio
import os
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Any

from openai import OpenAI

from client import NegotiationEnv
from models import NegotiationAction

# Load environment variables from .env file if it exists
# This allows running `python inference.py` directly without needing run_inference.sh
try:
    from dotenv import load_dotenv

    # Look for .env file in the same directory as this script
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    # python-dotenv not installed, skip (will rely on environment variables)
    pass

# Environment configuration
IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")

API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = "negotiation_env"
# MAX_STEPS removed — loop uses task_config["max_rounds"] per task (see ALL_TASKS)
TEMPERATURE = 0.3
MAX_TOKENS = 512

# ---------------------------------------------------------------------------
# Task configurations — must match tasks defined in openenv.yaml
# ---------------------------------------------------------------------------

# All available tasks (used when running locally without NEGOTIATION_TASK set)
ALL_TASKS = [
    {
        "name": "easy_conceder",
        "strategy_name": "conceder",
        "seed": 42,
        "max_rounds": 10,
        "description": "Easy: Conceder opponent who readily accepts reasonable offers",
    },
    {
        "name": "medium_tft",
        "strategy_name": "tit_for_tat",
        "seed": 42,
        "max_rounds": 10,
        "description": "Medium: Tit-for-Tat opponent who mirrors your concession rate",
    },
    {
        "name": "hard_hardliner",
        "strategy_name": "hardliner",
        "seed": 42,
        "max_rounds": 15,
        "description": "Hard: Hardliner opponent who barely concedes",
    },
]

# Map task names to their config for fast lookup
TASK_MAP = {t["name"]: t for t in ALL_TASKS}

# The hackathon evaluator sets NEGOTIATION_TASK to run a specific task.
# If not set, run all tasks (useful for local testing).
TASK_NAME_ENV = os.getenv("NEGOTIATION_TASK") or os.getenv("MY_ENV_V4_TASK")

# Resolve which tasks to run in this execution
if TASK_NAME_ENV:
    if TASK_NAME_ENV not in TASK_MAP:
        print(
            f"[DEBUG] Unknown task '{TASK_NAME_ENV}'. "
            f"Available: {list(TASK_MAP.keys())}. Defaulting to easy_conceder.",
            flush=True,
        )
        TASKS = [TASK_MAP["easy_conceder"]]
    else:
        # Single task mode — exactly what the evaluator expects
        TASKS = [TASK_MAP[TASK_NAME_ENV]]
else:
    # No task specified — run all (local testing mode)
    TASKS = ALL_TASKS

# System prompt for LLM negotiation
SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert negotiation agent in a multi-issue bilateral negotiation.

    ISSUES (all normalized [0, 1]):
    - price, quantity, delivery_days, warranty_months, payment_terms

    ROLE-BASED PREFERENCES:
    - Buyer wants: LOW price, HIGH quantity, LOW delivery_days, HIGH warranty_months, HIGH payment_terms
    - Seller wants: HIGH price, LOW quantity, HIGH delivery_days, LOW warranty_months, LOW payment_terms

    ACTIONS (respond with JSON only, no other text):
    1. Offer: {"action_type": "offer", "offer": {"price": 0.3, "quantity": 0.8, "delivery_days": 0.2, "warranty_months": 0.9, "payment_terms": 0.7}}
    2. Accept: {"action_type": "accept"}

    CRITICAL RULES — FOLLOW EXACTLY:

    1. NEVER RETRACT. Every new offer must concede from your previous offer. Never go backwards.

    2. CONCEDE STRATEGICALLY BY WEIGHT:
       - LOW-weight issues (weight < 0.15): concede 0.10-0.15 per round. These are cheap to give.
       - MEDIUM-weight issues (0.15-0.30): concede 0.05-0.08 per round.
       - HIGH-weight issues (weight > 0.30): concede only 0.01-0.03 per round. Protect these.

    3. WHEN TO ACCEPT:
       - Accept ONLY when the observation says "Accepting is good" or "accepting is reasonable".
       - Otherwise, keep making offers.

    4. OPENING OFFER:
       - Round 1: Set each issue to your ideal extreme (buyer: price=0.05, quantity=0.95,
         delivery_days=0.05, warranty_months=0.95, payment_terms=0.95).

    5. CONCESSION PACE:
       - You MUST make meaningful concessions each round. Moving 0.01 is NOT enough.
       - Target moving at least 0.05 total utility per round across all issues.
       - In the final 30% of rounds, double your concession rate.

    6. NEVER use "reject" action. A bad deal beats no deal.

    Respond with valid JSON only.
    """
).strip()


def log_start(task: str, env: str, model: str) -> None:
    """Log episode start."""
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    """Log each step."""
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """Log episode end."""
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def format_observation(obs: Any, offer_history: List[Dict[str, Any]]) -> str:
    """Format observation into a prompt for the LLM."""
    # Sort weights to highlight what matters most
    sorted_weights = sorted(obs.agent_weights.items(), key=lambda x: x[1], reverse=True)
    weights_str = ", ".join(f"{k}={v:.2f}" for k, v in sorted_weights)

    # Compute accept threshold
    reservation = obs.agent_reservation_utility
    aspiration = obs.agent_aspiration_utility
    accept_threshold = reservation + 0.3 * (aspiration - reservation)

    # Build history analysis
    history_lines = []
    if offer_history:
        agent_utils = [
            h["agent_utility"] for h in offer_history if h.get("agent_utility") is not None
        ]
        cp_utils = [
            h["cp_utility_of_agent_offer"]
            for h in offer_history
            if h.get("cp_utility_of_agent_offer") is not None
        ]

        if len(agent_utils) >= 2:
            trend = agent_utils[-1] - agent_utils[-2]
            history_lines.append(
                f"  Your utility trend: {agent_utils[-2]:.3f} -> {agent_utils[-1]:.3f} ({'improving' if trend > 0 else 'declining'})"
            )
        if agent_utils:
            history_lines.append(f"  Your best utility so far: {max(agent_utils):.3f}")

        # Show counterpart concession pattern
        cp_offer_utils = [
            h.get("cp_offer_utility_for_agent")
            for h in offer_history
            if h.get("cp_offer_utility_for_agent") is not None
        ]
        if len(cp_offer_utils) >= 2:
            cp_trend = cp_offer_utils[-1] - cp_offer_utils[0]
            history_lines.append(
                f"  Counterpart's offers to you: {' -> '.join(f'{u:.3f}' for u in cp_offer_utils)} (total movement: {cp_trend:+.3f})"
            )
            if abs(cp_trend) < 0.02 * len(cp_offer_utils):
                history_lines.append(
                    "  ** Counterpart is STUBBORN — concede only on low-weight issues **"
                )
            elif cp_trend > 0.05 * len(cp_offer_utils):
                history_lines.append("  ** Counterpart is CONCEDING — match their pace **")

    history_block = "\n".join(history_lines) if history_lines else "  No history yet."

    # Format last offers compactly
    def fmt_offer(offer: Optional[Dict[str, float]]) -> str:
        if not offer:
            return "None"
        return ", ".join(f"{k}={v:.2f}" for k, v in offer.items())

    accept_util_str = (
        f"{obs.agent_utility_if_accept:.3f}" if obs.agent_utility_if_accept is not None else "N/A"
    )
    own_util_str = (
        f"{obs.agent_utility_of_last_offer:.3f}"
        if obs.agent_utility_of_last_offer is not None
        else "N/A"
    )

    # Build the guidance on accept
    accept_guidance = ""
    if obs.agent_utility_if_accept is not None:
        if obs.rounds_remaining <= 1 and obs.agent_utility_if_accept >= reservation:
            accept_guidance = "-> FINAL ROUND: accepting is reasonable."
        elif obs.agent_utility_if_accept >= accept_threshold:
            accept_guidance = "-> Above your accept threshold. Accepting is good."
        else:
            gap = accept_threshold - obs.agent_utility_if_accept
            accept_guidance = f"-> Below accept threshold by {gap:.3f}. Keep negotiating."

    # Build per-issue concession guidance based on weights
    concession_lines = []
    if obs.agent_last_offer and obs.counterpart_last_offer:
        max_w = max(obs.agent_weights.values()) if obs.agent_weights else 1.0
        # Determine pace multiplier based on remaining rounds
        pace = 1.5 if obs.rounds_remaining <= obs.max_rounds * 0.3 else 1.0
        role = obs.agent_role

        for issue, w in sorted(obs.agent_weights.items(), key=lambda x: x[1]):
            last_val = obs.agent_last_offer.get(issue, 0.5)
            cp_val = obs.counterpart_last_offer.get(issue, 0.5)
            gap_to_cp = abs(cp_val - last_val)

            # Compute recommended concession based on weight
            if w / max_w < 0.3:  # Low weight — concede aggressively
                step_size = min(0.15 * pace, gap_to_cp * 0.4)
            elif w / max_w < 0.6:  # Medium weight
                step_size = min(0.07 * pace, gap_to_cp * 0.2)
            else:  # High weight — concede minimally
                step_size = min(0.02 * pace, gap_to_cp * 0.1)

            # Determine direction
            buyer_prefers_low = issue in ("price", "delivery_days")
            if role == "buyer":
                target = last_val + step_size if buyer_prefers_low else last_val - step_size
            else:
                target = last_val - step_size if buyer_prefers_low else last_val + step_size
            target = max(0.0, min(1.0, target))

            label = (
                "LOW-COST" if w / max_w < 0.3 else ("MEDIUM" if w / max_w < 0.6 else "HIGH-VALUE")
            )
            concession_lines.append(
                f"  {issue} (w={w:.2f}, {label}): {last_val:.2f} -> {target:.2f}"
            )

    concession_block = (
        "\n".join(concession_lines)
        if concession_lines
        else "  Make your opening offer at your ideal values."
    )

    obs_text = textwrap.dedent(
        f"""
        ROUND {obs.round_number}/{obs.max_rounds} ({obs.rounds_remaining} remaining) | Role: {obs.agent_role}

        ISSUE WEIGHTS (highest priority first): {weights_str}
        RESERVATION (walk-away): {reservation:.3f} | ASPIRATION (ideal): {aspiration:.3f}
        ACCEPT THRESHOLD: {accept_threshold:.3f}

        YOUR LAST OFFER: {fmt_offer(obs.agent_last_offer)}  (your utility: {own_util_str})
        THEIR LAST OFFER: {fmt_offer(obs.counterpart_last_offer)}  (your utility if accept: {accept_util_str})
        {accept_guidance}

        RECOMMENDED NEXT OFFER (concede per-issue):
        {concession_block}

        NEGOTIATION HISTORY:
        {history_block}

        Follow the recommended concessions closely. Respond with JSON only.
        """
    ).strip()
    return obs_text


def parse_llm_response(response_text: str) -> NegotiationAction:
    """Parse LLM response into a NegotiationAction.

    Handles three response formats:
    1. Raw JSON:          {"action_type": "offer", "offer": {...}}
    2. Markdown blocks:   ```json ... ```
    3. Reasoning models:  <thinking text> ... {"action_type": ...}
                          (Nemotron, DeepSeek-R1, etc. that prepend reasoning)
    """
    import json
    import re

    text = response_text.strip()

    # Step 1 — strip markdown code blocks if present
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    elif "```" in text:
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

    # Step 2 — try direct JSON parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Step 3 — reasoning model fallback:
        # scan the full original response for any JSON object containing "action_type"
        data = None
        original = response_text.strip()

        # Walk the string tracking brace depth to find all {...} blocks
        depth = 0
        start = -1
        candidates = []
        for i, char in enumerate(original):
            if char == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start != -1:
                    chunk = original[start : i + 1]
                    try:
                        parsed = json.loads(chunk)
                        if "action_type" in parsed:
                            candidates.append(parsed)
                    except json.JSONDecodeError:
                        pass
                    start = -1

        if candidates:
            # Use the last valid JSON found — after any reasoning preamble
            data = candidates[-1]
        else:
            # Total fallback: hardcoded default offer
            return NegotiationAction(
                action_type="offer",
                offer={
                    "price": 0.4,
                    "quantity": 0.6,
                    "delivery_days": 0.4,
                    "warranty_months": 0.6,
                    "payment_terms": 0.5,
                },
            )

    action_type = data.get("action_type", "offer")

    if action_type == "accept":
        return NegotiationAction(action_type="accept")
    elif action_type == "reject":
        return NegotiationAction(action_type="reject")
    else:
        offer = data.get("offer", {})
        # Ensure all issues have values
        default_offer = {
            "price": 0.5,
            "quantity": 0.5,
            "delivery_days": 0.5,
            "warranty_months": 0.5,
            "payment_terms": 0.5,
        }
        for key in default_offer:
            if key not in offer:
                offer[key] = default_offer[key]
            else:
                # Clamp to [0, 1]
                offer[key] = max(0.0, min(1.0, float(offer[key])))

        return NegotiationAction(action_type="offer", offer=offer)


def format_action_str(action: NegotiationAction) -> str:
    """Format action for logging."""
    if action.action_type == "accept":
        return "accept()"
    elif action.action_type == "reject":
        return "reject()"
    else:
        offer_parts = [f"{k}={v:.2f}" for k, v in (action.offer or {}).items()]
        return f"offer({','.join(offer_parts)})"


def enforce_monotonic_concession(
    new_offer: Dict[str, float],
    last_offer: Optional[Dict[str, float]],
    role: str,
    weights: Optional[Dict[str, float]] = None,
    ensure_progress: bool = True,
) -> Dict[str, float]:
    """
    Prevent retractions and ensure minimum progress each round.

    Clamps any issue that moves against concession direction, then ensures
    the offer actually progresses by adding minimum concessions on low-weight issues.
    """
    if last_offer is None:
        return new_offer

    # Conceding = moving TOWARD counterpart's preference
    buyer_concession_direction = {
        "price": 1,  # buyer concedes by raising price
        "quantity": -1,  # buyer concedes by lowering quantity
        "delivery_days": 1,  # buyer concedes by accepting slower delivery
        "warranty_months": -1,  # buyer concedes by accepting less warranty
        "payment_terms": -1,  # buyer concedes by accepting earlier payment
    }

    fixed = dict(new_offer)
    for issue, direction in buyer_concession_direction.items():
        if issue not in fixed or issue not in last_offer:
            continue

        if role == "seller":
            direction = -direction

        delta = fixed[issue] - last_offer[issue]

        # Clamp retractions
        if direction > 0 and delta < 0:
            fixed[issue] = last_offer[issue]
        elif direction < 0 and delta > 0:
            fixed[issue] = last_offer[issue]

    # Ensure minimum progress: if offer is identical to last, nudge low-weight issues
    if ensure_progress and weights and fixed == last_offer:
        sorted_issues = sorted(weights.items(), key=lambda x: x[1])
        for issue, w in sorted_issues[:3]:  # Nudge up to 3 lowest-weight issues
            direction = buyer_concession_direction.get(issue, 1)
            if role == "seller":
                direction = -direction
            nudge = 0.03 * direction
            fixed[issue] = max(0.0, min(1.0, fixed[issue] + nudge))

    return fixed


def should_accept_heuristic(obs: Any) -> bool:
    """Decide whether to accept based on utility thresholds."""
    if obs.agent_utility_if_accept is None:
        return False

    reservation = obs.agent_reservation_utility
    aspiration = obs.agent_aspiration_utility
    util = obs.agent_utility_if_accept

    # Final round: accept anything above reservation
    if obs.rounds_remaining <= 1:
        return util >= reservation

    # Normal rounds: accept if above threshold
    threshold = reservation + 0.3 * (aspiration - reservation)
    return util >= threshold


def get_model_action(
    client: OpenAI,
    obs: Any,
    offer_history: List[Dict[str, Any]],
) -> NegotiationAction:
    """Get action from LLM based on observation."""
    # Check if we should accept before even asking the LLM
    if should_accept_heuristic(obs):
        return NegotiationAction(action_type="accept")

    # Deadline panic: on the last round, if accept isn't viable, make a big concession
    if obs.rounds_remaining <= 1 and obs.agent_last_offer and obs.counterpart_last_offer:
        # Move 50% toward counterpart to try to close the deal
        offer = {}
        max_w = max(obs.agent_weights.values()) if obs.agent_weights else 1.0
        for issue in obs.agent_last_offer:
            agent_val = obs.agent_last_offer[issue]
            cp_val = obs.counterpart_last_offer[issue]
            w = obs.agent_weights.get(issue, 0.2)
            factor = 0.15 + 0.35 * (1.0 - w / max_w)  # 0.15 for high-weight, 0.50 for low
            offer[issue] = agent_val + factor * (cp_val - agent_val)
        return NegotiationAction(action_type="offer", offer=offer)

    user_prompt = format_observation(obs, offer_history)

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        action = parse_llm_response(text)
        if action is None:
            print(f"[DEBUG] Failed to parse LLM response: {text[:100]}", flush=True)
            action = _make_concession_offer(obs)
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        action = _make_concession_offer(obs)

    # If LLM wants to accept, verify with heuristic
    if action.action_type == "accept":
        if obs.agent_utility_if_accept is not None:
            reservation = obs.agent_reservation_utility
            # Block accept if utility is below reservation (always bad)
            if obs.agent_utility_if_accept < reservation:
                # Override: make a moderate concession offer instead
                action = _make_concession_offer(obs)
        return action

    # Never reject — override to a concession offer
    if action.action_type == "reject":
        action = _make_concession_offer(obs)

    # Enforce monotonic concessions (no retractions) and ensure progress
    if action.offer and obs.agent_last_offer:
        action = NegotiationAction(
            action_type="offer",
            offer=enforce_monotonic_concession(
                action.offer,
                obs.agent_last_offer,
                obs.agent_role,
                weights=obs.agent_weights,
                ensure_progress=True,
            ),
        )

    return action


def _make_concession_offer(obs: Any) -> NegotiationAction:
    """Generate a fallback concession offer based on current state.

    Concedes MORE on low-weight issues (cheap to give) and LESS on
    high-weight issues (expensive to give), preserving agent utility.
    """
    weights = getattr(obs, "agent_weights", {})
    role = getattr(obs, "agent_role", "buyer")

    if obs.agent_last_offer and obs.counterpart_last_offer:
        offer = {}
        max_weight = max(weights.values()) if weights else 1.0
        for issue in obs.agent_last_offer:
            agent_val = obs.agent_last_offer[issue]
            cp_val = obs.counterpart_last_offer[issue]
            # Weight-scaled concession: low-weight issues concede more
            w = weights.get(issue, 0.2)
            # Concession factor: 0.30 for lowest weight, 0.05 for highest weight
            factor = 0.05 + 0.25 * (1.0 - w / max_weight)
            offer[issue] = agent_val + factor * (cp_val - agent_val)
        return NegotiationAction(action_type="offer", offer=offer)
    else:
        # First offer: start aggressively in our favor
        if role == "buyer":
            return NegotiationAction(
                action_type="offer",
                offer={
                    "price": 0.10,
                    "quantity": 0.90,
                    "delivery_days": 0.10,
                    "warranty_months": 0.90,
                    "payment_terms": 0.80,
                },
            )
        else:
            return NegotiationAction(
                action_type="offer",
                offer={
                    "price": 0.90,
                    "quantity": 0.10,
                    "delivery_days": 0.90,
                    "warranty_months": 0.10,
                    "payment_terms": 0.20,
                },
            )


async def run_task(
    client: OpenAI,
    task_config: Dict[str, Any],
) -> float:
    """Run a single task and return the final score."""
    task_name = task_config["name"]
    strategy_name = task_config["strategy_name"]
    seed = task_config["seed"]
    max_rounds = task_config["max_rounds"]

    offer_history: List[Dict[str, Any]] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    # Connect to environment: use Docker locally, or direct connection in HF Spaces
    if IMAGE_NAME:
        env = await NegotiationEnv.from_docker_image(IMAGE_NAME)
    else:
        # HF Spaces: server is already running on localhost:8000
        env = NegotiationEnv(base_url="http://localhost:8000")

    try:
        # Reset environment with task-specific parameters
        result = await env.reset(
            seed=seed,
            strategy_name=strategy_name,
            max_rounds=max_rounds,
        )

        for step in range(1, task_config["max_rounds"] + 1):
            if result.done:
                break

            obs = result.observation

            # Get action from LLM
            action = get_model_action(client, obs, offer_history)
            action_str = format_action_str(action)

            # Execute action
            result = await env.step(action)

            reward = result.reward or 0.0
            done = result.done
            error = None  # Negotiation env doesn't have action errors

            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            # Track rich history for the next observation
            new_obs = result.observation
            history_entry: Dict[str, Any] = {
                "step": step,
                "action": action_str,
                "reward": reward,
                "agent_utility": new_obs.agent_utility_of_last_offer if new_obs else None,
                "cp_utility_of_agent_offer": None,
                "cp_offer_utility_for_agent": new_obs.agent_utility_if_accept if new_obs else None,
            }
            offer_history.append(history_entry)

            if done:
                break

        # Final score is the terminal reward (last reward in list)
        if rewards:
            score = rewards[-1]
        else:
            score = 0.0

        # Clamp score to [0, 1]
        score = max(0.0, min(1.0, score))

        # Success if we got a deal with reasonable utility
        success = score >= 0.5

    except Exception as e:
        print(f"[DEBUG] Task error: {e}", flush=True)
        score = 0.0
        success = False
    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error (container cleanup): {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


async def main() -> None:
    """
    Run task(s) and report scores.

    In single-task mode (NEGOTIATION_TASK env var set): runs exactly one task,
    emitting one [START]...[END] block. This is the evaluator's expected pattern.

    In multi-task mode (no env var): runs all 3 tasks sequentially for local testing.
    """
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    total_score = 0.0
    single_task_mode = TASK_NAME_ENV is not None

    for task_config in TASKS:
        if not single_task_mode:
            # Only print separators in multi-task (local testing) mode
            print(f"\n{'=' * 60}", flush=True)
            print(f"Running task: {task_config['name']}", flush=True)
            print(f"Description: {task_config['description']}", flush=True)
            print(f"{'=' * 60}\n", flush=True)

        score = await run_task(client, task_config)
        total_score += score

        if not single_task_mode:
            print(
                f"\nTask {task_config['name']} completed with score: {score:.2f}\n",
                flush=True,
            )

    if not single_task_mode:
        # Summary only shown in multi-task local testing mode
        average_score = total_score / len(TASKS) if TASKS else 0.0
        print(f"\n{'=' * 60}", flush=True)
        print(f"FINAL RESULTS", flush=True)
        print(f"{'=' * 60}", flush=True)
        print(f"Total tasks: {len(TASKS)}", flush=True)
        print(f"Total score: {total_score:.2f}", flush=True)
        print(f"Average score: {average_score:.2f}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
