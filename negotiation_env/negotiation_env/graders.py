"""
Grader functions for NegotiationEnv tasks.

Each grader takes the episode final state (as a dict from /state endpoint)
and returns a normalized score in [0.0, 1.0].

These are referenced in openenv.yaml under tasks[].grader.fn
"""

from typing import Any, Dict, Optional


def _extract_grader_output(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract grader output dict from state, handling both nested and flat formats."""
    # State may come as a dict from JSON deserialization
    grader = state.get("grader")
    if grader is None:
        return None
    if isinstance(grader, dict):
        return grader
    # If it's already a GraderOutput object (direct env usage)
    try:
        return grader.model_dump()
    except AttributeError:
        return dict(grader)


def grade_easy_conceder(state: Dict[str, Any]) -> float:
    """
    Grader for easy_conceder task.

    Scores based on:
    - Whether a deal was reached (primary signal)
    - Agent's utility relative to BATNA (secondary)

    Returns float in [0.0, 1.0].
    """
    grader = _extract_grader_output(state)

    if grader is None:
        # No grader output means episode ended abnormally
        return 0.0

    deal_reached = grader.get("deal_reached", False)

    if not deal_reached:
        return 0.0

    # Agent utility scaled to [0.5, 1.0] for deals above BATNA
    agent_utility = grader.get("agent_utility", 0.0)

    # Easy task: reward any deal, scale by utility quality
    score = min(1.0, 0.4 + 0.6 * agent_utility)
    return max(0.0, float(score))


def grade_medium_tft(state: Dict[str, Any]) -> float:
    """
    Grader for medium_tft task.

    Scores based on:
    - Deal reached (primary)
    - Joint surplus (efficiency of the deal)
    - Agent utility (quality for agent)

    Returns float in [0.0, 1.0].
    """
    grader = _extract_grader_output(state)

    if grader is None:
        return 0.0

    deal_reached = grader.get("deal_reached", False)

    if not deal_reached:
        return 0.0

    agent_utility = grader.get("agent_utility", 0.0)
    pareto_efficiency = grader.get("pareto_efficiency", 0.0)

    # Medium task: reward deals that are both good for agent AND efficient
    score = 0.5 * agent_utility + 0.5 * pareto_efficiency
    return max(0.0, min(1.0, float(score)))


def grade_hard_hardliner(state: Dict[str, Any]) -> float:
    """
    Grader for hard_hardliner task.

    Scores based on:
    - Deal reached (necessary for any positive score)
    - Agent utility (highly weighted — hardliner rarely gives good deals)
    - Negotiation efficiency (rewarding faster deals)

    Returns float in [0.0, 1.0].
    """
    grader = _extract_grader_output(state)

    if grader is None:
        return 0.0

    deal_reached = grader.get("deal_reached", False)

    if not deal_reached:
        # Hard task: small flat partial credit for attempting (grader may be None on no-deal)
        return 0.05

    agent_utility = grader.get("agent_utility", 0.0)
    negotiation_efficiency = grader.get("negotiation_efficiency", 1.0)

    # Hard task: high weight on agent utility, bonus for fast resolution
    # negotiation_efficiency = rounds_used/rounds_available (lower = faster)
    speed_bonus = max(0.0, 1.0 - negotiation_efficiency) * 0.1
    score = 0.9 * agent_utility + speed_bonus
    return max(0.0, min(1.0, float(score)))
