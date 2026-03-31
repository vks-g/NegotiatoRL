"""
Counterpart negotiation strategies for the Negotiation Environment.

Each strategy class implements deterministic behavior given a seed,
allowing reproducible negotiations for training and evaluation.

All strategies inherit from CounterpartStrategy ABC and implement:
- generate_offer(): Produce a counteroffer based on current state
- should_accept(): Decide whether to accept the agent's offer
- get_name(): Return the strategy identifier
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import random
from dataclasses import dataclass

from .rewards import compute_utility, _party_prefers_low


@dataclass
class NegotiationContext:
    """Context information passed to strategies for decision-making."""

    round_number: int
    max_rounds: int
    counterpart_role: str  # 'buyer' or 'seller'
    counterpart_weights: Dict[str, float]
    counterpart_reservation: float
    counterpart_aspiration: float
    issue_specs: Dict[str, dict]
    agent_last_offer: Optional[Dict[str, float]]
    counterpart_last_offer: Optional[Dict[str, float]]
    offer_history: List[dict]


class CounterpartStrategy(ABC):
    """
    Abstract base class for counterpart negotiation strategies.

    All strategies must be deterministic given a seed for reproducibility.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the strategy with an optional random seed.

        Args:
            seed: Random seed for reproducible behavior
        """
        self._seed = seed
        self._rng = random.Random(seed)

    @abstractmethod
    def get_name(self) -> str:
        """Return the strategy identifier."""
        pass

    @abstractmethod
    def generate_offer(self, context: NegotiationContext) -> Dict[str, float]:
        """
        Generate a counteroffer based on the current negotiation context.

        Args:
            context: Current negotiation state and history

        Returns:
            Dict mapping issue names to proposed values [0, 1]
        """
        pass

    @abstractmethod
    def should_accept(self, context: NegotiationContext) -> bool:
        """
        Decide whether to accept the agent's current offer.

        Args:
            context: Current negotiation state and history

        Returns:
            True if the strategy accepts the agent's offer
        """
        pass

    def _compute_own_utility(self, offer: Dict[str, float], context: NegotiationContext) -> float:
        """Compute the counterpart's utility for a given offer."""
        return compute_utility(
            offer, context.counterpart_weights, context.counterpart_role, context.issue_specs
        )

    def _get_aspiration_offer(self, context: NegotiationContext) -> Dict[str, float]:
        """Generate an offer at the counterpart's aspiration level."""
        offer = {}
        for issue_name in context.counterpart_weights:
            # Set each issue to counterpart's preferred extreme
            prefers_low = _party_prefers_low(issue_name, context.counterpart_role)
            offer[issue_name] = 0.0 if prefers_low else 1.0
        return offer

    def _get_reservation_offer(self, context: NegotiationContext) -> Dict[str, float]:
        """Generate an offer at the counterpart's reservation level (BATNA)."""
        # Start from midpoint and adjust
        offer = {name: 0.5 for name in context.counterpart_weights}
        return offer

    def _interpolate_offer(
        self,
        offer_a: Dict[str, float],
        offer_b: Dict[str, float],
        alpha: float,
    ) -> Dict[str, float]:
        """Interpolate between two offers: result = (1-alpha)*a + alpha*b."""
        result = {}
        for issue_name in offer_a:
            val_a = offer_a.get(issue_name, 0.5)
            val_b = offer_b.get(issue_name, 0.5)
            result[issue_name] = (1 - alpha) * val_a + alpha * val_b
        return result


# =============================================================================
# Strategy Implementations
# =============================================================================


class HardlinerStrategy(CounterpartStrategy):
    """
    Hardliner: Barely concedes, rejects anything near agent's aspiration.

    Behavior:
    - Starts at aspiration and makes tiny concessions (2% per round)
    - Only accepts offers giving > 85% of aspiration utility
    - Tests agent's patience and ability to extract concessions

    Difficulty: HARD
    """

    CONCESSION_RATE = 0.02  # 2% concession per round
    ACCEPTANCE_THRESHOLD = 0.85  # Requires 85% of aspiration to accept

    def get_name(self) -> str:
        return "hardliner"

    def generate_offer(self, context: NegotiationContext) -> Dict[str, float]:
        aspiration_offer = self._get_aspiration_offer(context)
        midpoint_offer = {name: 0.5 for name in context.counterpart_weights}

        # Calculate how far to move from aspiration (very slowly)
        progress = min(1.0, context.round_number * self.CONCESSION_RATE)

        # Add small random noise for variety (seeded)
        noise = self._rng.uniform(-0.02, 0.02)
        progress = max(0.0, min(1.0, progress + noise))

        return self._interpolate_offer(aspiration_offer, midpoint_offer, progress)

    def should_accept(self, context: NegotiationContext) -> bool:
        if context.agent_last_offer is None:
            return False

        utility = self._compute_own_utility(context.agent_last_offer, context)
        threshold = context.counterpart_aspiration * self.ACCEPTANCE_THRESHOLD

        return utility >= threshold


class ConcederStrategy(CounterpartStrategy):
    """
    Conceder: Rapidly moves toward midpoint, accepts easily.

    Behavior:
    - Starts at aspiration but concedes 15% per round
    - Accepts offers at or above reservation (BATNA)
    - Easy opponent for testing basic negotiation skills

    Difficulty: EASY
    """

    CONCESSION_RATE = 0.15  # 15% concession per round

    def get_name(self) -> str:
        return "conceder"

    def generate_offer(self, context: NegotiationContext) -> Dict[str, float]:
        aspiration_offer = self._get_aspiration_offer(context)
        midpoint_offer = {name: 0.5 for name in context.counterpart_weights}

        # Rapid movement toward midpoint
        progress = min(1.0, context.round_number * self.CONCESSION_RATE)

        # Small noise
        noise = self._rng.uniform(-0.03, 0.03)
        progress = max(0.0, min(1.0, progress + noise))

        return self._interpolate_offer(aspiration_offer, midpoint_offer, progress)

    def should_accept(self, context: NegotiationContext) -> bool:
        if context.agent_last_offer is None:
            return False

        utility = self._compute_own_utility(context.agent_last_offer, context)

        # Accept anything at or above reservation
        return utility >= context.counterpart_reservation


class TitForTatStrategy(CounterpartStrategy):
    """
    Tit-for-Tat: Mirrors the agent's concession rate.

    Behavior:
    - Matches agent's concession pattern (with 90% mirror factor)
    - If agent concedes a lot, counterpart concedes similarly
    - If agent is stubborn, counterpart is equally stubborn
    - Minimum 1% concession per round to prevent deadlock

    Difficulty: MEDIUM
    """

    MIRROR_FACTOR = 0.9  # How closely to mirror agent's concessions
    MIN_CONCESSION = 0.01  # Minimum concession to prevent complete deadlock

    def get_name(self) -> str:
        return "tit_for_tat"

    def generate_offer(self, context: NegotiationContext) -> Dict[str, float]:
        aspiration_offer = self._get_aspiration_offer(context)

        # If no previous offers, start at aspiration with small concession
        if context.counterpart_last_offer is None:
            progress = self.MIN_CONCESSION + self._rng.uniform(0, 0.05)
            midpoint = {name: 0.5 for name in context.counterpart_weights}
            return self._interpolate_offer(aspiration_offer, midpoint, progress)

        # Calculate agent's concession from their previous offer (if any)
        agent_concession = self._estimate_agent_concession(context)

        # Mirror the concession
        our_concession = max(self.MIN_CONCESSION, agent_concession * self.MIRROR_FACTOR)

        # Apply concession from current position
        midpoint = {name: 0.5 for name in context.counterpart_weights}

        # Move from current position toward midpoint
        return self._interpolate_offer(context.counterpart_last_offer, midpoint, our_concession)

    def _estimate_agent_concession(self, context: NegotiationContext) -> float:
        """Estimate how much the agent conceded in their last move."""
        if len(context.offer_history) < 2:
            return 0.05  # Default small concession

        # Find agent's last two offers
        agent_offers = [
            h["offer"]
            for h in context.offer_history
            if h.get("party") == "agent" and h.get("offer") is not None
        ]

        if len(agent_offers) < 2:
            return 0.05

        prev_offer = agent_offers[-2]
        curr_offer = agent_offers[-1]

        # Compute utility change (from counterpart's perspective)
        prev_util = self._compute_own_utility(prev_offer, context)
        curr_util = self._compute_own_utility(curr_offer, context)

        # Positive = agent gave ground (good for counterpart)
        concession = curr_util - prev_util

        return max(0.0, concession)

    def should_accept(self, context: NegotiationContext) -> bool:
        if context.agent_last_offer is None:
            return False

        utility = self._compute_own_utility(context.agent_last_offer, context)

        # Accept if offer is between reservation and aspiration midpoint
        midpoint = (context.counterpart_reservation + context.counterpart_aspiration) / 2
        return utility >= midpoint


class RandomStrategy(CounterpartStrategy):
    """
    Random: Uniform random offers within feasible space.

    Behavior:
    - Generates random offers (seeded for reproducibility)
    - Accepts randomly with probability based on offer quality
    - Tests agent's ability to handle unpredictable opponents

    Difficulty: UNPREDICTABLE
    """

    def get_name(self) -> str:
        return "random"

    def generate_offer(self, context: NegotiationContext) -> Dict[str, float]:
        # Generate random offer within feasible range
        offer = {}
        for issue_name in context.counterpart_weights:
            # Bias toward counterpart's preferred direction
            prefers_low = _party_prefers_low(issue_name, context.counterpart_role)

            if prefers_low:
                # Sample biased toward low values
                offer[issue_name] = self._rng.betavariate(2, 5)  # Skewed low
            else:
                # Sample biased toward high values
                offer[issue_name] = self._rng.betavariate(5, 2)  # Skewed high

        return offer

    def should_accept(self, context: NegotiationContext) -> bool:
        if context.agent_last_offer is None:
            return False

        utility = self._compute_own_utility(context.agent_last_offer, context)

        # Probabilistic acceptance based on utility
        # Higher utility = higher chance of acceptance
        acceptance_prob = utility**2  # Quadratic to favor good offers

        return self._rng.random() < acceptance_prob


class TimePressuredStrategy(CounterpartStrategy):
    """
    Time-Pressured: Makes large concessions as deadline approaches.

    Behavior:
    - Small concessions early (2% per round)
    - Panic threshold at 30% rounds remaining
    - After panic: 25% concession per round
    - Simulates negotiators with deadline pressure

    Difficulty: MEDIUM-HARD (patient agents can exploit)
    """

    EARLY_CONCESSION = 0.02  # 2% early
    LATE_CONCESSION = 0.25  # 25% when panicking
    PANIC_THRESHOLD = 0.3  # Panic when 30% rounds remain

    def get_name(self) -> str:
        return "time_pressured"

    def generate_offer(self, context: NegotiationContext) -> Dict[str, float]:
        aspiration_offer = self._get_aspiration_offer(context)
        midpoint_offer = {name: 0.5 for name in context.counterpart_weights}

        # Calculate time pressure
        rounds_remaining_ratio = (context.max_rounds - context.round_number) / context.max_rounds
        is_panicking = rounds_remaining_ratio <= self.PANIC_THRESHOLD

        # Calculate cumulative progress
        if is_panicking:
            # Fast concessions in panic mode
            panic_rounds = int(context.max_rounds * self.PANIC_THRESHOLD)
            normal_progress = (context.max_rounds - panic_rounds) * self.EARLY_CONCESSION
            panic_progress = (
                context.round_number - (context.max_rounds - panic_rounds)
            ) * self.LATE_CONCESSION
            progress = normal_progress + panic_progress
        else:
            # Slow concessions early
            progress = context.round_number * self.EARLY_CONCESSION

        # Add noise
        noise = self._rng.uniform(-0.02, 0.02)
        progress = max(0.0, min(1.0, progress + noise))

        return self._interpolate_offer(aspiration_offer, midpoint_offer, progress)

    def should_accept(self, context: NegotiationContext) -> bool:
        if context.agent_last_offer is None:
            return False

        utility = self._compute_own_utility(context.agent_last_offer, context)

        # Acceptance threshold drops as deadline approaches
        rounds_remaining_ratio = (context.max_rounds - context.round_number) / context.max_rounds

        if rounds_remaining_ratio <= self.PANIC_THRESHOLD:
            # Panic mode: accept anything above reservation
            return utility >= context.counterpart_reservation
        else:
            # Normal mode: higher standards
            threshold = context.counterpart_reservation + 0.3 * (
                context.counterpart_aspiration - context.counterpart_reservation
            )
            return utility >= threshold


# =============================================================================
# Strategy Factory
# =============================================================================

STRATEGY_CLASSES = {
    "hardliner": HardlinerStrategy,
    "conceder": ConcederStrategy,
    "tit_for_tat": TitForTatStrategy,
    "random": RandomStrategy,
    "time_pressured": TimePressuredStrategy,
}


def create_strategy(name: str, seed: Optional[int] = None) -> CounterpartStrategy:
    """
    Factory function to create a counterpart strategy by name.

    Args:
        name: Strategy identifier (hardliner, conceder, tit_for_tat, random, time_pressured)
        seed: Random seed for reproducibility

    Returns:
        Initialized CounterpartStrategy instance

    Raises:
        ValueError: If strategy name is unknown
    """
    if name not in STRATEGY_CLASSES:
        available = ", ".join(STRATEGY_CLASSES.keys())
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")

    return STRATEGY_CLASSES[name](seed=seed)


def get_random_strategy(rng: random.Random, seed: Optional[int] = None) -> CounterpartStrategy:
    """
    Select a random strategy using the provided RNG.

    Args:
        rng: Random number generator for strategy selection
        seed: Seed for the strategy's internal RNG

    Returns:
        Randomly selected CounterpartStrategy instance
    """
    name = rng.choice(list(STRATEGY_CLASSES.keys()))
    return create_strategy(name, seed=seed)


def get_all_strategy_names() -> List[str]:
    """Return list of all available strategy names."""
    return list(STRATEGY_CLASSES.keys())
