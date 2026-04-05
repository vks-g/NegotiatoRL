"""
Pure reward functions for the Negotiation Environment.

All functions take only numeric inputs (no environment state objects)
and return values in [0.0, 1.0] range for GRPO compatibility.

These functions are designed to be unit-testable in isolation.
"""

from typing import List, Dict, Tuple

# Small epsilon to prevent division by zero
EPS = 1e-6


# =============================================================================
# Terminal Reward Functions (applied when episode ends)
# =============================================================================


def deal_reward(
    deal_reached: bool,
    agent_utility: float,
    agent_reservation: float,
) -> float:
    """
    Terminal reward based on whether a deal was reached and its quality.

    Args:
        deal_reached: Whether a deal was successfully concluded
        agent_utility: Agent's utility from the final deal [0, 1]
        agent_reservation: Agent's BATNA (minimum acceptable utility) [0, 1]

    Returns:
        Reward in [0.0, 1.0]:
        - 0.0 if no deal (walk-out or deadline breach)
        - 0.2-0.5 for deals below BATNA (partial credit for near-miss)
        - 0.5-1.0 for deals at or above BATNA (scaled by how much above)

    Design rationale:
        - Strong signal for getting deals above reservation
        - Partial credit prevents policy collapse on hard negotiations
        - Smooth gradient from poor deals to excellent deals
    """
    if not deal_reached:
        return 0.0

    if agent_utility >= agent_reservation:
        # Good deal: scale from 0.5 (at BATNA) to 1.0 (at maximum utility)
        headroom = 1.0 - agent_reservation + EPS
        above_batna = agent_utility - agent_reservation
        return min(1.0, 0.5 + 0.5 * (above_batna / headroom))
    else:
        # Below BATNA: partial credit, scales from 0.0 to 0.5
        if agent_reservation < EPS:
            return 0.2
        return 0.2 + 0.3 * (agent_utility / agent_reservation)


def utility_score(
    agent_utility: float,
    agent_aspiration: float,
) -> float:
    """
    Terminal reward measuring how good the deal was relative to aspiration.

    Args:
        agent_utility: Agent's utility from the final deal [0, 1]
        agent_aspiration: Agent's aspiration level (ideal target) [0, 1]

    Returns:
        Reward in [0.0, 1.0]:
        - Ratio of achieved utility to aspiration
        - Capped at 1.0 (exceeding aspiration doesn't give extra reward)

    Design rationale:
        - Encourages ambitious negotiations
        - Rewards getting a GOOD deal, not just any deal
        - Complements deal_reward which focuses on BATNA threshold
    """
    if agent_aspiration < EPS:
        return 1.0 if agent_utility > EPS else 0.0

    return min(1.0, agent_utility / agent_aspiration)


# =============================================================================
# Shaping Reward Functions (applied every step for gradient signal)
# =============================================================================


def efficiency_reward(
    current_joint_utility: float,
    pareto_frontier_utility: float,
    previous_joint_utility: float,
) -> float:
    """
    Shaping reward for moving closer to the Pareto frontier.

    Args:
        current_joint_utility: Sum of both parties' utilities from current proposal
        pareto_frontier_utility: Maximum achievable joint utility (Pareto optimal)
        previous_joint_utility: Joint utility from previous step

    Returns:
        Reward in [0.0, 1.0]:
        - 0.5 baseline (no change)
        - > 0.5 for improving joint value (finding integrative solutions)
        - < 0.5 for destroying joint value (zero-sum fighting)

    Design rationale:
        - Encourages value creation, not just value claiming
        - Provides gradient signal even before deal is reached
        - Teaches agent that negotiation can be win-win
    """
    if pareto_frontier_utility < EPS:
        return 0.5  # Neutral if no frontier defined

    # Normalized improvement toward Pareto frontier
    improvement = (current_joint_utility - previous_joint_utility) / pareto_frontier_utility

    # Map to [0, 1] with 0.5 as baseline
    return max(0.0, min(1.0, 0.5 + 0.5 * improvement))


def concession_quality(
    agent_concession_vector: List[float],
    agent_weights: List[float],
) -> float:
    """
    Shaping reward for strategic concessions (concede on low-priority issues).

    Args:
        agent_concession_vector: Per-issue concession amounts (positive = gave ground)
        agent_weights: Per-issue importance weights for the agent [0, 1]

    Returns:
        Reward in [0.0, 1.0]:
        - 0.5 baseline (no movement)
        - > 0.5 for strategic concessions (low-priority issues)
        - < 0.5 for poor concessions (high-priority issues)

    Design rationale:
        - Teaches agent to trade issues strategically
        - Concede on issues you care less about
        - Hold firm on issues that matter most
        - Penalizes erratic or irrational concession patterns
    """
    if not agent_concession_vector or not agent_weights:
        return 0.5  # Neutral if no data

    total_concession = sum(abs(c) for c in agent_concession_vector)

    if total_concession < EPS:
        return 0.5  # No movement, neutral

    # Calculate quality: high score for conceding on low-weight issues
    # weighted_concession measures "good" concessions (on less important issues)
    weighted_quality = 0.0
    for concession, weight in zip(agent_concession_vector, agent_weights):
        if concession > 0:  # Agent conceded on this issue
            # Reward higher for low-weight issues (1 - weight)
            weighted_quality += concession * (1.0 - weight)
        elif concession < 0:  # Agent demanded more (took back)
            # Penalty higher for low-weight issues (demanding on unimportant things is bad)
            weighted_quality -= abs(concession) * (1.0 - weight)

    # Normalize by total movement
    quality_ratio = weighted_quality / total_concession

    # Map to [0, 1] with 0.5 as baseline
    return max(0.0, min(1.0, 0.5 + 0.5 * quality_ratio))


# =============================================================================
# Utility Computation Functions
# =============================================================================


def compute_utility(
    offer: Dict[str, float],
    weights: Dict[str, float],
    role: str,
    issue_specs: Dict[str, dict],
) -> float:
    """
    Compute a party's utility for a given offer.

    Args:
        offer: Dict mapping issue names to values [0, 1] normalized
        weights: Dict mapping issue names to importance weights (sum to 1)
        role: 'buyer' or 'seller' (determines preference direction)
        issue_specs: Dict with issue specifications for direction mapping

    Returns:
        Utility in [0.0, 1.0] as weighted sum of issue utilities

    Issue preference directions:
        - price: buyer wants low (0.0 = good), seller wants high (1.0 = good)
        - quantity: buyer wants high, seller wants low
        - delivery_days: buyer wants low (fast), seller wants high (slow)
        - warranty_months: buyer wants high (long), seller wants low (short)
        - payment_terms: buyer wants high (delayed), seller wants low (upfront)
    """
    if not offer or not weights:
        return 0.0

    total_utility = 0.0

    for issue_name, value in offer.items():
        if issue_name not in weights:
            continue

        weight = weights[issue_name]

        # Determine if this party prefers high or low values
        prefers_low = _party_prefers_low(issue_name, role)

        # Convert value to utility based on preference direction
        if prefers_low:
            issue_utility = 1.0 - value  # Lower value = higher utility
        else:
            issue_utility = value  # Higher value = higher utility

        total_utility += weight * issue_utility

    return max(0.0, min(1.0, total_utility))


def _party_prefers_low(issue_name: str, role: str) -> bool:
    """Determine if a party prefers lower values for an issue."""
    # Define preference directions for each role
    buyer_prefers_low = {
        "price": True,  # Buyer wants low price
        "quantity": False,  # Buyer wants high quantity
        "delivery_days": True,  # Buyer wants fast (low days) delivery
        "warranty_months": False,  # Buyer wants long (high) warranty
        "payment_terms": False,  # Buyer wants delayed (high) payment terms
    }

    if issue_name not in buyer_prefers_low:
        return False  # Default: prefer high

    if role == "buyer":
        return buyer_prefers_low[issue_name]
    else:  # seller
        return not buyer_prefers_low[issue_name]


def compute_joint_utility(
    offer: Dict[str, float],
    agent_weights: Dict[str, float],
    counterpart_weights: Dict[str, float],
    agent_role: str,
    issue_specs: Dict[str, dict],
) -> float:
    """
    Compute the joint utility (sum of both parties' utilities) for an offer.

    Args:
        offer: Dict mapping issue names to values
        agent_weights: Agent's importance weights
        counterpart_weights: Counterpart's importance weights
        agent_role: 'buyer' or 'seller'
        issue_specs: Issue specifications

    Returns:
        Joint utility in [0.0, 2.0] (sum of two [0, 1] utilities)
    """
    counterpart_role = "seller" if agent_role == "buyer" else "buyer"

    agent_utility = compute_utility(offer, agent_weights, agent_role, issue_specs)
    counterpart_utility = compute_utility(offer, counterpart_weights, counterpart_role, issue_specs)

    return agent_utility + counterpart_utility


def compute_pareto_frontier_utility(
    agent_weights: Dict[str, float],
    counterpart_weights: Dict[str, float],
    agent_role: str,
    issue_specs: Dict[str, dict],
    num_samples: int = 100,
    seed: int = 42,
) -> float:
    """
    Estimate the Pareto frontier's maximum joint utility through sampling.

    Args:
        agent_weights: Agent's importance weights
        counterpart_weights: Counterpart's importance weights
        agent_role: 'buyer' or 'seller'
        issue_specs: Issue specifications
        num_samples: Number of random offers to sample
        seed: Random seed for reproducibility (default: 42)

    Returns:
        Estimated maximum achievable joint utility [0.0, 2.0]

    Note:
        This is an approximation. True Pareto computation would require
        multi-objective optimization. Sampling is sufficient for reward shaping.
        Uses a local seeded RNG for reproducibility - does not affect global state.
    """
    import random

    # Use a local seeded RNG for reproducibility (does not affect global state)
    rng = random.Random(seed)

    max_joint = 0.0
    issue_names = list(agent_weights.keys())

    for _ in range(num_samples):
        # Generate random offer using local seeded RNG
        offer = {name: rng.random() for name in issue_names}

        joint = compute_joint_utility(
            offer, agent_weights, counterpart_weights, agent_role, issue_specs
        )
        max_joint = max(max_joint, joint)

    return max_joint


def compute_concession_vector(
    current_offer: Dict[str, float],
    previous_offer: Dict[str, float],
    role: str,
) -> List[float]:
    """
    Compute the concession vector between two offers.

    Args:
        current_offer: The new offer
        previous_offer: The previous offer
        role: 'buyer' or 'seller' (determines concession direction)

    Returns:
        List of concession amounts per issue (positive = gave ground)
    """
    if not previous_offer or not current_offer:
        return []

    concessions = []

    for issue_name in current_offer:
        if issue_name not in previous_offer:
            concessions.append(0.0)
            continue

        current_val = current_offer[issue_name]
        previous_val = previous_offer[issue_name]

        # Determine concession direction based on preference
        prefers_low = _party_prefers_low(issue_name, role)

        if prefers_low:
            # Agent prefers low, so moving higher is a concession
            concession = current_val - previous_val
        else:
            # Agent prefers high, so moving lower is a concession
            concession = previous_val - current_val

        concessions.append(concession)

    return concessions


# =============================================================================
# Aggregate Reward Function
# =============================================================================


def compute_step_reward(
    is_terminal: bool,
    deal_reached: bool,
    agent_utility: float,
    agent_reservation: float,
    agent_aspiration: float,
    current_joint_utility: float,
    previous_joint_utility: float,
    pareto_frontier_utility: float,
    agent_concession_vector: List[float],
    agent_weights: List[float],
    shaping_weight: float = 0.4,
    terminal_weight: float = 0.6,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute the aggregate reward for a step with component breakdown.

    Args:
        is_terminal: Whether this step ends the episode
        deal_reached: Whether a deal was reached (if terminal)
        agent_utility: Agent's utility from current proposal
        agent_reservation: Agent's BATNA
        agent_aspiration: Agent's aspiration level
        current_joint_utility: Current joint utility
        previous_joint_utility: Previous joint utility
        pareto_frontier_utility: Maximum achievable joint utility
        agent_concession_vector: Concession amounts per issue
        agent_weights: Agent's importance weights as list
        shaping_weight: Weight for shaping rewards (default 0.4)
        terminal_weight: Weight for terminal rewards (default 0.6)

    Returns:
        Tuple of (aggregate_reward, breakdown_dict) where:
        - aggregate_reward is in [0.0, 1.0]
        - breakdown_dict shows individual reward components
    """
    breakdown = {}

    # Compute shaping rewards (always)
    eff_reward = efficiency_reward(
        current_joint_utility, pareto_frontier_utility, previous_joint_utility
    )
    conc_quality = concession_quality(agent_concession_vector, agent_weights)

    breakdown["efficiency_reward"] = eff_reward
    breakdown["concession_quality"] = conc_quality

    if is_terminal:
        # Compute terminal rewards
        deal_rew = deal_reward(deal_reached, agent_utility, agent_reservation)
        util_score = utility_score(agent_utility, agent_aspiration)

        breakdown["deal_reward"] = deal_rew
        breakdown["utility_score"] = util_score

        if deal_reached:
            # Weighted combination of all four rewards
            aggregate = (
                0.35 * deal_rew + 0.35 * util_score + 0.15 * eff_reward + 0.15 * conc_quality
            )
        else:
            # No deal: heavy penalty, but preserve some shaping signal
            aggregate = 0.1 * (eff_reward + conc_quality) / 2

        breakdown["is_terminal"] = True
        breakdown["deal_reached"] = deal_reached
    else:
        # Non-terminal: only shaping rewards
        aggregate = 0.5 * eff_reward + 0.5 * conc_quality
        breakdown["is_terminal"] = False

    aggregate = max(0.0, min(1.0, aggregate))
    breakdown["aggregate"] = aggregate

    return aggregate, breakdown
