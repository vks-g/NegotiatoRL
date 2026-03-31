"""
Core Negotiation Environment implementation.

Implements the OpenEnv Environment interface with:
- reset(): Initialize a new negotiation episode
- step(): Process agent action and counterpart response
- state: Return full episode state including grader output

Supports concurrent sessions via SUPPORTS_CONCURRENT_SESSIONS = True.
All randomness is seeded for reproducibility.
"""

import random
import uuid
from typing import Any, Dict, List, Optional

from openenv.core.env_server import Environment

from ..models import (
    NegotiationAction,
    NegotiationObservation,
    NegotiationState,
    IssueSpec,
    OfferRecord,
    GraderOutput,
)
from ..strategies import (
    CounterpartStrategy,
    NegotiationContext,
    create_strategy,
    get_random_strategy,
    get_all_strategy_names,
)
from ..rewards import (
    compute_utility,
    compute_joint_utility,
    compute_pareto_frontier_utility,
    compute_concession_vector,
    compute_step_reward,
)


# =============================================================================
# Default Issue Space Configuration
# =============================================================================

DEFAULT_ISSUES = {
    "price": IssueSpec(
        name="price",
        issue_type="continuous",
        min_value=0.0,
        max_value=1.0,
        description="Normalized price (0=lowest, 1=highest)",
    ),
    "quantity": IssueSpec(
        name="quantity",
        issue_type="discrete",
        min_value=0.1,
        max_value=1.0,
        description="Normalized quantity (0.1=1 unit, 1.0=10 units)",
    ),
    "delivery_days": IssueSpec(
        name="delivery_days",
        issue_type="ordinal",
        min_value=0.0,
        max_value=1.0,
        options=["1", "7", "14", "30", "60"],
        description="Delivery timeline (0=1 day, 1=60 days)",
    ),
    "warranty_months": IssueSpec(
        name="warranty_months",
        issue_type="ordinal",
        min_value=0.0,
        max_value=1.0,
        options=["0", "6", "12", "24", "36"],
        description="Warranty duration (0=none, 1=36 months)",
    ),
    "payment_terms": IssueSpec(
        name="payment_terms",
        issue_type="categorical",
        min_value=0.0,
        max_value=1.0,
        options=["upfront", "net30", "net60", "installments"],
        description="Payment schedule (0=upfront, 1=installments)",
    ),
}


# =============================================================================
# Environment Implementation
# =============================================================================


class NegotiationEnvironment(Environment):
    """
    Multi-Issue Bilateral Negotiation Environment.

    The agent plays one party (buyer or seller) in a negotiation against
    a parameterized counterpart strategy. Each episode is a complete
    negotiation with defined issues, reservation values, and time pressure.

    Features:
    - 5 negotiation issues with different types
    - 5 counterpart strategies (hardliner, conceder, tit-for-tat, random, time-pressured)
    - 4 GRPO-compatible reward signals
    - Comprehensive grader for hackathon evaluation
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    DEFAULT_MAX_ROUNDS = 10
    DEFAULT_PARETO_SAMPLES = 100

    def __init__(self):
        """Initialize the environment with default empty state."""
        super().__init__()
        self._state = NegotiationState()
        self._strategy: Optional[CounterpartStrategy] = None
        self._rng = random.Random()
        self._pareto_frontier_utility = 1.5  # Default estimate
        self._previous_joint_utility = 0.0
        self._issues_dict: Dict[str, dict] = {}

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        strategy_name: Optional[str] = None,
        agent_role: Optional[str] = None,
        **kwargs: Any,
    ) -> NegotiationObservation:
        """
        Initialize a new negotiation episode.

        Args:
            seed: Random seed for reproducibility
            episode_id: Optional custom episode identifier
            max_rounds: Maximum rounds before deadline (default: 10)
            strategy_name: Force specific counterpart strategy (default: random)
            agent_role: Force agent role ('buyer' or 'seller', default: random)
            **kwargs: Additional configuration options

        Returns:
            Initial NegotiationObservation with agent's private information
        """
        # Initialize RNG
        if seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        # Generate episode ID
        ep_id = episode_id or str(uuid.uuid4())

        # Select agent role
        if agent_role is None:
            agent_role = self._rng.choice(["buyer", "seller"])
        counterpart_role = "seller" if agent_role == "buyer" else "buyer"

        # Generate issue weights (sum to 1.0)
        agent_weights = self._generate_weights()
        counterpart_weights = self._generate_weights()

        # Generate reservation and aspiration utilities
        agent_reservation = self._rng.uniform(0.25, 0.45)
        agent_aspiration = self._rng.uniform(0.7, 0.9)
        counterpart_reservation = self._rng.uniform(0.25, 0.45)
        counterpart_aspiration = self._rng.uniform(0.7, 0.9)

        # Select counterpart strategy
        if strategy_name:
            self._strategy = create_strategy(strategy_name, seed=seed)
        else:
            self._strategy = get_random_strategy(self._rng, seed=seed)

        # Prepare issues dict for utility computation
        self._issues_dict = {name: spec.model_dump() for name, spec in DEFAULT_ISSUES.items()}

        # Estimate Pareto frontier
        self._pareto_frontier_utility = compute_pareto_frontier_utility(
            agent_weights,
            counterpart_weights,
            agent_role,
            self._issues_dict,
            num_samples=self.DEFAULT_PARETO_SAMPLES,
        )
        self._previous_joint_utility = 0.0

        # Initialize state
        self._state = NegotiationState(
            episode_id=ep_id,
            step_count=0,
            counterpart_strategy=self._strategy.get_name(),
            counterpart_weights=counterpart_weights,
            counterpart_reservation_utility=counterpart_reservation,
            counterpart_aspiration_utility=counterpart_aspiration,
            agent_role=agent_role,
            agent_weights=agent_weights,
            agent_reservation_utility=agent_reservation,
            agent_aspiration_utility=agent_aspiration,
            max_rounds=max_rounds,
            seed=seed,
            offer_history=[],
            deal_reached=False,
            terminal_reason=None,
            grader=None,
            last_reward_breakdown={},
        )

        # Build initial observation
        return NegotiationObservation(
            done=False,
            reward=None,
            round_number=1,
            rounds_remaining=max_rounds - 1,
            max_rounds=max_rounds,
            agent_role=agent_role,
            agent_weights=agent_weights,
            agent_reservation_utility=agent_reservation,
            agent_aspiration_utility=agent_aspiration,
            issues=DEFAULT_ISSUES,
            agent_last_offer=None,
            counterpart_last_offer=None,
            counterpart_last_action="none",
            agent_utility_if_accept=None,
            agent_utility_of_last_offer=None,
            total_offers_made=0,
            agent_offer_count=0,
            counterpart_offer_count=0,
            recent_offers=[],
            message=f"Negotiation started. You are the {agent_role}. Make your first offer!",
        )

    def step(
        self,
        action: NegotiationAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> NegotiationObservation:
        """
        Process agent's action and counterpart's response.

        Args:
            action: Agent's action (offer, accept, or reject)
            timeout_s: Optional timeout (not used in this implementation)
            **kwargs: Additional options

        Returns:
            NegotiationObservation with updated state and reward
        """
        self._state.step_count += 1
        round_number = self._state.step_count

        # Get previous state for reward computation
        agent_last_offer_before = self._get_agent_last_offer()

        # Process agent's action
        if action.action_type == "reject":
            return self._handle_agent_reject(action, round_number)
        elif action.action_type == "accept":
            return self._handle_agent_accept(action, round_number)
        else:  # offer
            return self._handle_agent_offer(action, round_number, agent_last_offer_before)

    @property
    def state(self) -> NegotiationState:
        """Return the full episode state including hidden information."""
        return self._state

    # =========================================================================
    # Action Handlers
    # =========================================================================

    def _handle_agent_reject(
        self,
        action: NegotiationAction,
        round_number: int,
    ) -> NegotiationObservation:
        """Handle agent's reject action (terminates with no deal)."""
        # Record the rejection
        record = OfferRecord(
            round_number=round_number,
            party="agent",
            action_type="reject",
            offer=None,
            utility_for_agent=None,
            utility_for_counterpart=None,
            message=action.message,
        )
        self._state.offer_history.append(record)

        # Terminate episode
        self._state.deal_reached = False
        self._state.terminal_reason = "agent_reject"

        # Compute terminal reward (0.0 for rejection)
        reward, breakdown = self._compute_terminal_reward(deal_reached=False)
        self._state.last_reward_breakdown = breakdown

        # Generate grader output
        self._state.grader = self._generate_grader_output()

        return self._build_observation(
            done=True,
            reward=reward,
            round_number=round_number,
            counterpart_action="none",
            message="You rejected the negotiation. No deal reached.",
        )

    def _handle_agent_accept(
        self,
        action: NegotiationAction,
        round_number: int,
    ) -> NegotiationObservation:
        """Handle agent's accept action (accepts counterpart's last offer)."""
        counterpart_last_offer = self._get_counterpart_last_offer()

        if counterpart_last_offer is None:
            # Can't accept if no offer to accept
            return self._build_observation(
                done=False,
                reward=0.0,
                round_number=round_number,
                counterpart_action="none",
                message="Cannot accept: no counterpart offer to accept. Make an offer instead.",
            )

        # Record the acceptance
        agent_utility = self._compute_agent_utility(counterpart_last_offer)
        counterpart_utility = self._compute_counterpart_utility(counterpart_last_offer)

        record = OfferRecord(
            round_number=round_number,
            party="agent",
            action_type="accept",
            offer=counterpart_last_offer,
            utility_for_agent=agent_utility,
            utility_for_counterpart=counterpart_utility,
            message=action.message,
        )
        self._state.offer_history.append(record)

        # Terminate episode with deal
        self._state.deal_reached = True
        self._state.terminal_reason = "agent_accept"

        # Compute terminal reward
        reward, breakdown = self._compute_terminal_reward(
            deal_reached=True,
            agent_utility=agent_utility,
        )
        self._state.last_reward_breakdown = breakdown

        # Generate grader output
        self._state.grader = self._generate_grader_output()

        return self._build_observation(
            done=True,
            reward=reward,
            round_number=round_number,
            counterpart_action="none",
            message=f"Deal reached! You accepted the offer. Your utility: {agent_utility:.3f}",
        )

    def _handle_agent_offer(
        self,
        action: NegotiationAction,
        round_number: int,
        agent_previous_offer: Optional[Dict[str, float]],
    ) -> NegotiationObservation:
        """Handle agent's offer and generate counterpart response."""
        assert action.offer is not None, "Offer required for action_type='offer'"

        # Normalize and validate offer
        offer = self._normalize_offer(action.offer)

        # Compute utilities
        agent_utility = self._compute_agent_utility(offer)
        counterpart_utility = self._compute_counterpart_utility(offer)

        # Record agent's offer
        record = OfferRecord(
            round_number=round_number,
            party="agent",
            action_type="offer",
            offer=offer,
            utility_for_agent=agent_utility,
            utility_for_counterpart=counterpart_utility,
            message=action.message,
        )
        self._state.offer_history.append(record)

        # Build context for counterpart strategy
        context = self._build_strategy_context(round_number)

        # Check if counterpart accepts
        if self._strategy.should_accept(context):
            return self._handle_counterpart_accept(offer, round_number, agent_utility)

        # Check if deadline reached
        if round_number >= self._state.max_rounds:
            return self._handle_deadline(round_number)

        # Generate counterpart's counteroffer
        counteroffer = self._strategy.generate_offer(context)
        counteroffer = self._normalize_offer(counteroffer)

        # Compute counteroffer utilities
        co_agent_utility = self._compute_agent_utility(counteroffer)
        co_counterpart_utility = self._compute_counterpart_utility(counteroffer)

        # Record counterpart's offer
        co_record = OfferRecord(
            round_number=round_number,
            party="counterpart",
            action_type="offer",
            offer=counteroffer,
            utility_for_agent=co_agent_utility,
            utility_for_counterpart=co_counterpart_utility,
            message=None,
        )
        self._state.offer_history.append(co_record)

        # Compute shaping reward
        current_joint = agent_utility + counterpart_utility
        concession_vector = []
        weight_list = []

        if agent_previous_offer:
            concession_vector = compute_concession_vector(
                offer, agent_previous_offer, self._state.agent_role
            )
            weight_list = [self._state.agent_weights.get(k, 0) for k in offer.keys()]

        reward, breakdown = compute_step_reward(
            is_terminal=False,
            deal_reached=False,
            agent_utility=agent_utility,
            agent_reservation=self._state.agent_reservation_utility,
            agent_aspiration=self._state.agent_aspiration_utility,
            current_joint_utility=current_joint,
            previous_joint_utility=self._previous_joint_utility,
            pareto_frontier_utility=self._pareto_frontier_utility,
            agent_concession_vector=concession_vector,
            agent_weights=weight_list,
        )

        self._previous_joint_utility = current_joint
        self._state.last_reward_breakdown = breakdown

        return self._build_observation(
            done=False,
            reward=reward,
            round_number=round_number,
            counterpart_action="offer",
            message=f"Counterpart countered. Your offer utility: {agent_utility:.3f}, "
            f"their offer utility for you: {co_agent_utility:.3f}",
        )

    def _handle_counterpart_accept(
        self,
        agent_offer: Dict[str, float],
        round_number: int,
        agent_utility: float,
    ) -> NegotiationObservation:
        """Handle counterpart accepting agent's offer."""
        # Record counterpart's acceptance
        record = OfferRecord(
            round_number=round_number,
            party="counterpart",
            action_type="accept",
            offer=agent_offer,
            utility_for_agent=agent_utility,
            utility_for_counterpart=self._compute_counterpart_utility(agent_offer),
            message=None,
        )
        self._state.offer_history.append(record)

        # Terminate episode with deal
        self._state.deal_reached = True
        self._state.terminal_reason = "counterpart_accept"

        # Compute terminal reward
        reward, breakdown = self._compute_terminal_reward(
            deal_reached=True,
            agent_utility=agent_utility,
        )
        self._state.last_reward_breakdown = breakdown

        # Generate grader output
        self._state.grader = self._generate_grader_output()

        return self._build_observation(
            done=True,
            reward=reward,
            round_number=round_number,
            counterpart_action="accept",
            message=f"Deal reached! Counterpart accepted your offer. Your utility: {agent_utility:.3f}",
        )

    def _handle_deadline(self, round_number: int) -> NegotiationObservation:
        """Handle deadline reached without deal."""
        self._state.deal_reached = False
        self._state.terminal_reason = "deadline"

        # Compute terminal reward (0.0 for deadline)
        reward, breakdown = self._compute_terminal_reward(deal_reached=False)
        self._state.last_reward_breakdown = breakdown

        # Generate grader output
        self._state.grader = self._generate_grader_output()

        return self._build_observation(
            done=True,
            reward=reward,
            round_number=round_number,
            counterpart_action="none",
            message="Deadline reached. No deal.",
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _generate_weights(self) -> Dict[str, float]:
        """Generate random issue weights that sum to 1.0."""
        issue_names = list(DEFAULT_ISSUES.keys())
        raw_weights = [self._rng.random() for _ in issue_names]
        total = sum(raw_weights)
        return {name: w / total for name, w in zip(issue_names, raw_weights)}

    def _normalize_offer(self, offer: Dict[str, float]) -> Dict[str, float]:
        """Ensure all offer values are in [0, 1] range."""
        normalized = {}
        for name in DEFAULT_ISSUES:
            value = offer.get(name, 0.5)  # Default to midpoint
            normalized[name] = max(0.0, min(1.0, float(value)))
        return normalized

    def _compute_agent_utility(self, offer: Dict[str, float]) -> float:
        """Compute agent's utility for an offer."""
        return compute_utility(
            offer,
            self._state.agent_weights,
            self._state.agent_role,
            self._issues_dict,
        )

    def _compute_counterpart_utility(self, offer: Dict[str, float]) -> float:
        """Compute counterpart's utility for an offer."""
        counterpart_role = "seller" if self._state.agent_role == "buyer" else "buyer"
        return compute_utility(
            offer,
            self._state.counterpart_weights,
            counterpart_role,
            self._issues_dict,
        )

    def _get_agent_last_offer(self) -> Optional[Dict[str, float]]:
        """Get the agent's most recent offer."""
        for record in reversed(self._state.offer_history):
            if record.party == "agent" and record.action_type == "offer":
                return record.offer
        return None

    def _get_counterpart_last_offer(self) -> Optional[Dict[str, float]]:
        """Get the counterpart's most recent offer."""
        for record in reversed(self._state.offer_history):
            if record.party == "counterpart" and record.action_type == "offer":
                return record.offer
        return None

    def _build_strategy_context(self, round_number: int) -> NegotiationContext:
        """Build context object for counterpart strategy."""
        counterpart_role = "seller" if self._state.agent_role == "buyer" else "buyer"

        return NegotiationContext(
            round_number=round_number,
            max_rounds=self._state.max_rounds,
            counterpart_role=counterpart_role,
            counterpart_weights=self._state.counterpart_weights,
            counterpart_reservation=self._state.counterpart_reservation_utility,
            counterpart_aspiration=self._state.counterpart_aspiration_utility,
            issue_specs=self._issues_dict,
            agent_last_offer=self._get_agent_last_offer(),
            counterpart_last_offer=self._get_counterpart_last_offer(),
            offer_history=[r.model_dump() for r in self._state.offer_history],
        )

    def _compute_terminal_reward(
        self,
        deal_reached: bool,
        agent_utility: float = 0.0,
    ) -> tuple:
        """Compute terminal reward with breakdown."""
        # Get concession data for final step
        agent_last = self._get_agent_last_offer()
        agent_offers = [
            r.offer
            for r in self._state.offer_history
            if r.party == "agent" and r.action_type == "offer" and r.offer
        ]

        concession_vector = []
        weight_list = []

        if len(agent_offers) >= 2:
            concession_vector = compute_concession_vector(
                agent_offers[-1], agent_offers[-2], self._state.agent_role
            )
            weight_list = [self._state.agent_weights.get(k, 0) for k in agent_offers[-1].keys()]

        # Compute joint utility at end
        current_joint = 0.0
        if deal_reached and agent_last:
            current_joint = compute_joint_utility(
                agent_last,
                self._state.agent_weights,
                self._state.counterpart_weights,
                self._state.agent_role,
                self._issues_dict,
            )

        return compute_step_reward(
            is_terminal=True,
            deal_reached=deal_reached,
            agent_utility=agent_utility,
            agent_reservation=self._state.agent_reservation_utility,
            agent_aspiration=self._state.agent_aspiration_utility,
            current_joint_utility=current_joint,
            previous_joint_utility=self._previous_joint_utility,
            pareto_frontier_utility=self._pareto_frontier_utility,
            agent_concession_vector=concession_vector,
            agent_weights=weight_list,
        )

    def _generate_grader_output(self) -> GraderOutput:
        """Generate comprehensive grader output for episode evaluation."""
        # Determine final deal details
        final_offer = None
        agent_utility = 0.0
        counterpart_utility = 0.0

        if self._state.deal_reached:
            # Find the accepted offer
            for record in reversed(self._state.offer_history):
                if record.action_type == "accept" and record.offer:
                    final_offer = record.offer
                    agent_utility = record.utility_for_agent or 0.0
                    counterpart_utility = record.utility_for_counterpart or 0.0
                    break

        # Get agent's first and final offers
        agent_offers = [
            r for r in self._state.offer_history if r.party == "agent" and r.action_type == "offer"
        ]

        first_offer_utility = agent_offers[0].utility_for_agent if agent_offers else 0.0
        final_offer_utility = agent_offers[-1].utility_for_agent if agent_offers else 0.0

        # Calculate total concessions
        total_agent_concession = 0.0
        total_counterpart_concession = 0.0

        if len(agent_offers) >= 2:
            total_agent_concession = (first_offer_utility or 0.0) - (final_offer_utility or 0.0)

        counterpart_offers = [
            r
            for r in self._state.offer_history
            if r.party == "counterpart" and r.action_type == "offer"
        ]
        if len(counterpart_offers) >= 2:
            first_cp = counterpart_offers[0].utility_for_counterpart or 0.0
            last_cp = counterpart_offers[-1].utility_for_counterpart or 0.0
            total_counterpart_concession = first_cp - last_cp

        # Calculate Pareto efficiency
        joint_surplus = agent_utility + counterpart_utility
        pareto_efficiency = (
            joint_surplus / self._pareto_frontier_utility
            if self._pareto_frontier_utility > 0
            else 0.0
        )

        return GraderOutput(
            deal_reached=self._state.deal_reached,
            agent_utility=agent_utility,
            counterpart_utility=counterpart_utility,
            joint_surplus=joint_surplus,
            rounds_used=self._state.step_count,
            rounds_available=self._state.max_rounds,
            strategy_detected=self._state.counterpart_strategy,
            pareto_efficiency=min(1.0, pareto_efficiency),
            negotiation_efficiency=self._state.step_count / self._state.max_rounds,
            agent_first_offer_utility=first_offer_utility or 0.0,
            agent_final_offer_utility=final_offer_utility or 0.0,
            total_agent_concession=max(0.0, total_agent_concession),
            total_counterpart_concession=max(0.0, total_counterpart_concession),
        )

    def _build_observation(
        self,
        done: bool,
        reward: float,
        round_number: int,
        counterpart_action: str,
        message: str,
    ) -> NegotiationObservation:
        """Build observation object from current state."""
        agent_last = self._get_agent_last_offer()
        counterpart_last = self._get_counterpart_last_offer()

        # Compute utilities for decision support
        agent_utility_if_accept = None
        if counterpart_last:
            agent_utility_if_accept = self._compute_agent_utility(counterpart_last)

        agent_utility_of_last = None
        if agent_last:
            agent_utility_of_last = self._compute_agent_utility(agent_last)

        # Count offers
        agent_offer_count = sum(
            1 for r in self._state.offer_history if r.party == "agent" and r.action_type == "offer"
        )
        counterpart_offer_count = sum(
            1
            for r in self._state.offer_history
            if r.party == "counterpart" and r.action_type == "offer"
        )

        # Get recent offers (last 6 for pattern recognition)
        recent = self._state.offer_history[-6:] if self._state.offer_history else []

        return NegotiationObservation(
            done=done,
            reward=reward,
            round_number=round_number,
            rounds_remaining=max(0, self._state.max_rounds - round_number),
            max_rounds=self._state.max_rounds,
            agent_role=self._state.agent_role,
            agent_weights=self._state.agent_weights,
            agent_reservation_utility=self._state.agent_reservation_utility,
            agent_aspiration_utility=self._state.agent_aspiration_utility,
            issues=DEFAULT_ISSUES,
            agent_last_offer=agent_last,
            counterpart_last_offer=counterpart_last,
            counterpart_last_action=counterpart_action,
            agent_utility_if_accept=agent_utility_if_accept,
            agent_utility_of_last_offer=agent_utility_of_last,
            total_offers_made=agent_offer_count + counterpart_offer_count,
            agent_offer_count=agent_offer_count,
            counterpart_offer_count=counterpart_offer_count,
            recent_offers=recent,
            message=message,
        )
