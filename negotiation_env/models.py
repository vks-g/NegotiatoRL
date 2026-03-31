"""
Pydantic models for the Negotiation Environment.

Defines the typed contracts for Actions, Observations, and State.
These models ensure type safety and enable IDE autocomplete.

IMPORTANT: Do NOT redefine 'done' or 'reward' in Observation (inherited from base).
IMPORTANT: Do NOT redefine 'episode_id' or 'step_count' in State (inherited from base).
"""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from openenv.core.env_server import Action, Observation, State


# =============================================================================
# Supporting Types
# =============================================================================


class IssueSpec(BaseModel):
    """Specification for a single negotiation issue."""

    name: str = Field(..., description="Issue identifier")
    issue_type: Literal["continuous", "discrete", "ordinal", "categorical"] = Field(
        ..., description="Type of issue determining valid values"
    )
    min_value: float = Field(0.0, description="Minimum value (for continuous/discrete)")
    max_value: float = Field(1.0, description="Maximum value (for continuous/discrete)")
    options: List[str] = Field(
        default_factory=list, description="Valid options (for categorical/ordinal issues)"
    )
    description: str = Field("", description="Human-readable description of the issue")


class OfferRecord(BaseModel):
    """Record of a single offer in the negotiation history."""

    round_number: int = Field(..., description="Round when this offer was made")
    party: Literal["agent", "counterpart"] = Field(..., description="Who made this offer")
    action_type: Literal["offer", "accept", "reject"] = Field(..., description="Type of action")
    offer: Optional[Dict[str, float]] = Field(
        None, description="Offer values if action_type is 'offer'"
    )
    utility_for_agent: Optional[float] = Field(None, description="Agent's utility for this offer")
    utility_for_counterpart: Optional[float] = Field(
        None, description="Counterpart's utility for this offer"
    )
    message: Optional[str] = Field(None, description="Optional message with the action")


class GraderOutput(BaseModel):
    """Structured evaluation output for hackathon LLM scoring."""

    deal_reached: bool = Field(..., description="Whether a deal was successfully reached")
    agent_utility: float = Field(
        ..., ge=0.0, le=1.0, description="Agent's utility from final deal (0-1)"
    )
    counterpart_utility: float = Field(
        ..., ge=0.0, le=1.0, description="Counterpart's utility from final deal (0-1)"
    )
    joint_surplus: float = Field(
        ..., ge=0.0, le=2.0, description="Sum of both parties' utilities (value creation)"
    )
    rounds_used: int = Field(..., ge=1, description="Number of rounds used in negotiation")
    rounds_available: int = Field(..., ge=1, description="Maximum rounds that were available")
    strategy_detected: str = Field(..., description="Which counterpart strategy was deployed")
    pareto_efficiency: float = Field(
        ..., ge=0.0, le=1.0, description="How close the deal is to the Pareto frontier (0-1)"
    )
    negotiation_efficiency: float = Field(
        ..., ge=0.0, le=1.0, description="rounds_used / rounds_available (lower = more efficient)"
    )
    agent_first_offer_utility: float = Field(
        ..., ge=0.0, le=1.0, description="Agent's utility from their first offer"
    )
    agent_final_offer_utility: float = Field(
        ..., ge=0.0, le=1.0, description="Agent's utility from the final accepted offer"
    )
    total_agent_concession: float = Field(
        ..., ge=0.0, description="Total utility conceded by agent throughout negotiation"
    )
    total_counterpart_concession: float = Field(
        ..., ge=0.0, description="Total utility conceded by counterpart throughout negotiation"
    )


# =============================================================================
# Core OpenEnv Types
# =============================================================================


class NegotiationAction(Action):
    """
    Action the agent can take in the negotiation.

    Three action types:
    - 'offer': Make an offer across all issues (requires offer dict)
    - 'accept': Accept the counterpart's last offer (ends episode with deal)
    - 'reject': Hard rejection, walk away (ends episode with no deal)
    """

    action_type: Literal["offer", "accept", "reject"] = Field(
        ..., description="Type of action to take"
    )
    offer: Optional[Dict[str, float]] = Field(
        None, description="Offer values for each issue (required when action_type='offer')"
    )
    message: Optional[str] = Field(
        None, max_length=500, description="Optional message with the action"
    )

    @field_validator("offer")
    @classmethod
    def validate_offer_present(
        cls, v: Optional[Dict[str, float]], info
    ) -> Optional[Dict[str, float]]:
        """Ensure offer is provided when action_type is 'offer'."""
        action_type = info.data.get("action_type")
        if action_type == "offer" and v is None:
            raise ValueError("offer dict is required when action_type is 'offer'")
        if action_type != "offer" and v is not None:
            raise ValueError("offer should be None when action_type is not 'offer'")
        return v


class NegotiationObservation(Observation):
    """
    Observation the agent receives after each step.

    Contains the agent's private information, the public issue space,
    the current negotiation state, and computed utilities.

    NOTE: 'done' and 'reward' are inherited from Observation base class.
    """

    # Current negotiation state
    round_number: int = Field(..., ge=1, description="Current round number (1-indexed)")
    rounds_remaining: int = Field(..., ge=0, description="Rounds left before deadline")
    max_rounds: int = Field(..., ge=1, description="Maximum rounds in this episode")

    # Agent's private information (counterpart doesn't see this)
    agent_role: Literal["buyer", "seller"] = Field(..., description="Agent's role in negotiation")
    agent_weights: Dict[str, float] = Field(
        ..., description="Agent's importance weights for each issue (sum to 1.0)"
    )
    agent_reservation_utility: float = Field(
        ..., ge=0.0, le=1.0, description="Agent's BATNA threshold (minimum acceptable utility)"
    )
    agent_aspiration_utility: float = Field(
        ..., ge=0.0, le=1.0, description="Agent's aspiration level (ideal utility target)"
    )

    # Issue space (shared knowledge)
    issues: Dict[str, IssueSpec] = Field(..., description="Specification of all negotiation issues")

    # Offer state
    agent_last_offer: Optional[Dict[str, float]] = Field(
        None, description="Agent's most recent offer (None if no offer yet)"
    )
    counterpart_last_offer: Optional[Dict[str, float]] = Field(
        None, description="Counterpart's most recent offer (None if no offer yet)"
    )
    counterpart_last_action: Literal["offer", "accept", "reject", "none"] = Field(
        "none", description="Counterpart's last action type"
    )

    # Computed utilities (to help agent decision-making)
    agent_utility_if_accept: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Agent's utility if they accept counterpart's current offer",
    )
    agent_utility_of_last_offer: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Agent's utility from their own last offer"
    )

    # History summary (condensed for context efficiency)
    total_offers_made: int = Field(0, ge=0, description="Total offers made by both parties")
    agent_offer_count: int = Field(0, ge=0, description="Number of offers made by agent")
    counterpart_offer_count: int = Field(
        0, ge=0, description="Number of offers made by counterpart"
    )

    # Recent history (last 3 offers for pattern recognition)
    recent_offers: List[OfferRecord] = Field(
        default_factory=list,
        max_length=6,
        description="Last 3 offers from each party for pattern recognition",
    )

    # Feedback message
    message: str = Field("", description="Feedback or status message from the environment")


class NegotiationState(State):
    """
    Full episode state including hidden information.

    This is accessible via the /state endpoint and contains:
    - Counterpart's hidden information (for post-episode analysis)
    - Full offer history
    - Grader output (populated at episode end)

    NOTE: 'episode_id' and 'step_count' are inherited from State base class.
    """

    # Hidden counterpart information (not shown to agent during episode)
    counterpart_strategy: str = Field("", description="Name of the counterpart strategy being used")
    counterpart_weights: Dict[str, float] = Field(
        default_factory=dict, description="Counterpart's importance weights for each issue"
    )
    counterpart_reservation_utility: float = Field(
        0.0, ge=0.0, le=1.0, description="Counterpart's BATNA threshold"
    )
    counterpart_aspiration_utility: float = Field(
        0.0, ge=0.0, le=1.0, description="Counterpart's aspiration level"
    )

    # Agent information (for completeness)
    agent_role: str = Field("", description="Agent's role in this episode")
    agent_weights: Dict[str, float] = Field(
        default_factory=dict, description="Agent's importance weights"
    )
    agent_reservation_utility: float = Field(0.0, ge=0.0, le=1.0)
    agent_aspiration_utility: float = Field(0.0, ge=0.0, le=1.0)

    # Episode configuration
    max_rounds: int = Field(10, ge=1, description="Maximum rounds for this episode")
    seed: Optional[int] = Field(None, description="Random seed used for this episode")

    # Full offer history
    offer_history: List[OfferRecord] = Field(
        default_factory=list, description="Complete history of all offers"
    )

    # Terminal state
    deal_reached: bool = Field(False, description="Whether a deal was reached")
    terminal_reason: Optional[str] = Field(
        None, description="Reason for episode termination (deal, reject, deadline)"
    )

    # Grader output (populated at episode end)
    grader: Optional[GraderOutput] = Field(
        None, description="Structured evaluation output (populated after episode ends)"
    )

    # Reward breakdown (for analysis)
    last_reward_breakdown: Dict[str, float] = Field(
        default_factory=dict, description="Breakdown of reward components from last step"
    )
