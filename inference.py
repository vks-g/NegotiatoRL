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
from typing import Dict, List, Optional, Any

from openai import OpenAI

from negotiation_env import NegotiationEnv, NegotiationAction

# Environment configuration
IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")

API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"
BENCHMARK = "negotiation_env"
MAX_STEPS = 10
TEMPERATURE = 0.7
MAX_TOKENS = 512

# Task configurations matching openenv.yaml
TASKS = [
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
        "max_rounds": 10,
        "description": "Hard: Hardliner opponent who barely concedes",
    },
]

# System prompt for LLM negotiation
SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert negotiation agent playing a multi-issue bilateral negotiation.
    
    GAME RULES:
    - You negotiate across 5 issues: price, quantity, delivery_days, warranty_months, payment_terms
    - Each issue value is normalized [0, 1]
    - Your goal is to maximize your utility while reaching a deal
    - You have limited rounds before deadline
    
    ACTIONS (respond with JSON):
    1. Make an offer:
       {"action_type": "offer", "offer": {"price": 0.3, "quantity": 0.8, "delivery_days": 0.2, "warranty_months": 0.9, "payment_terms": 0.7}}
    
    2. Accept counterpart's offer:
       {"action_type": "accept"}
    
    3. Reject and walk away (ends negotiation with no deal):
       {"action_type": "reject"}
    
    STRATEGY TIPS:
    - As buyer: prefer low price, high quantity, fast delivery, long warranty, delayed payment
    - As seller: prefer high price, low quantity, slow delivery, short warranty, upfront payment
    - Accept offers above your reservation utility
    - Make concessions on low-priority issues to get gains on high-priority ones
    - Watch the deadline - better to get a deal than no deal
    
    Always respond with valid JSON only. No explanations outside the JSON.
    """
).strip()


def log_start(task: str, env: str, model: str) -> None:
    """Log episode start."""
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
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
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def format_observation(obs: Any) -> str:
    """Format observation into a prompt for the LLM."""
    obs_text = textwrap.dedent(
        f"""
        CURRENT STATE:
        - Round: {obs.round_number} / {obs.max_rounds}
        - Rounds remaining: {obs.rounds_remaining}
        - Your role: {obs.agent_role}
        
        YOUR PRIVATE INFO:
        - Your weights (issue importance): {obs.agent_weights}
        - Your reservation utility (BATNA): {obs.agent_reservation_utility:.3f}
        - Your aspiration utility (ideal): {obs.agent_aspiration_utility:.3f}
        
        CURRENT OFFERS:
        - Your last offer: {obs.agent_last_offer or "None"}
        - Counterpart's last offer: {obs.counterpart_last_offer or "None"}
        - Counterpart's last action: {obs.counterpart_last_action}
        
        UTILITIES:
        - Your utility if you accept their offer: {obs.agent_utility_if_accept if obs.agent_utility_if_accept else "N/A"}
        - Your utility from your last offer: {obs.agent_utility_of_last_offer if obs.agent_utility_of_last_offer else "N/A"}
        
        MESSAGE: {obs.message}
        
        What action do you take? Respond with JSON only.
        """
    ).strip()
    return obs_text


def parse_llm_response(response_text: str) -> NegotiationAction:
    """Parse LLM response into a NegotiationAction."""
    import json
    import re

    # Try to extract JSON from response
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
    elif "```" in text:
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: make a default offer
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


def get_model_action(
    client: OpenAI,
    obs: Any,
    history: List[str],
) -> NegotiationAction:
    """Get action from LLM based on observation."""
    user_prompt = format_observation(obs)

    # Add recent history for context
    if history:
        history_text = "\nRECENT HISTORY:\n" + "\n".join(history[-4:])
        user_prompt += history_text

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
        return parse_llm_response(text)
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        # Fallback: make a reasonable offer
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


async def run_task(
    client: OpenAI,
    task_config: Dict[str, Any],
) -> float:
    """Run a single task and return the final score."""
    task_name = task_config["name"]
    strategy_name = task_config["strategy_name"]
    seed = task_config["seed"]
    max_rounds = task_config["max_rounds"]

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    env = await NegotiationEnv.from_docker_image(IMAGE_NAME)

    try:
        # Reset environment with task-specific parameters
        result = await env.reset(
            seed=seed,
            strategy_name=strategy_name,
            max_rounds=max_rounds,
        )

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            obs = result.observation

            # Get action from LLM
            action = get_model_action(client, obs, history)
            action_str = format_action_str(action)

            # Execute action
            result = await env.step(action)

            reward = result.reward or 0.0
            done = result.done
            error = None  # Negotiation env doesn't have action errors

            rewards.append(reward)
            steps_taken = step

            log_step(
                step=step, action=action_str, reward=reward, done=done, error=error
            )

            # Update history
            history.append(f"Step {step}: {action_str} -> reward {reward:+.2f}")

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
    """Run all tasks and report scores."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    total_score = 0.0

    for task_config in TASKS:
        print(f"\n{'=' * 60}", flush=True)
        print(f"Running task: {task_config['name']}", flush=True)
        print(f"Description: {task_config['description']}", flush=True)
        print(f"{'=' * 60}\n", flush=True)

        score = await run_task(client, task_config)
        total_score += score

        print(
            f"\nTask {task_config['name']} completed with score: {score:.2f}\n",
            flush=True,
        )

    average_score = total_score / len(TASKS) if TASKS else 0.0
    print(f"\n{'=' * 60}", flush=True)
    print(f"FINAL RESULTS", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"Total tasks: {len(TASKS)}", flush=True)
    print(f"Total score: {total_score:.2f}", flush=True)
    print(f"Average score: {average_score:.2f}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
