"""
WebSocket client for the Negotiation Environment.

Provides a type-safe interface for interacting with the negotiation
environment server. Implements the OpenEnv EnvClient interface.

Usage:
    from negotiation_env import NegotiationEnv, NegotiationAction

    # Async usage
    async with NegotiationEnv(base_url="http://localhost:8000") as env:
        result = await env.reset()
        result = await env.step(NegotiationAction(action_type="offer", offer={...}))

    # Sync usage (for notebooks/scripts)
    with NegotiationEnv(base_url="http://localhost:8000").sync() as env:
        result = env.reset()
        result = env.step(NegotiationAction(action_type="offer", offer={...}))
"""

from typing import Dict, Optional, Any

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from .models import (
    NegotiationAction,
    NegotiationObservation,
    NegotiationState,
    IssueSpec,
    OfferRecord,
    GraderOutput,
)


class NegotiationEnv(EnvClient[NegotiationAction, NegotiationObservation, NegotiationState]):
    """
    Client for the Negotiation RL Environment.

    Connects to a running NegotiationEnvironment server via WebSocket
    and provides type-safe methods for negotiation interactions.

    Args:
        base_url: URL of the environment server (e.g., "http://localhost:8000")
        **kwargs: Additional arguments passed to EnvClient

    Example:
        >>> env = NegotiationEnv(base_url="http://localhost:8000")
        >>> with env.sync() as sync_env:
        ...     result = sync_env.reset(seed=42, strategy_name="conceder")
        ...     while not result.done:
        ...         action = NegotiationAction(
        ...             action_type="offer",
        ...             offer={"price": 0.3, "quantity": 0.8, ...}
        ...         )
        ...         result = sync_env.step(action)
        ...     print(f"Final reward: {result.reward}")
    """

    def _step_payload(self, action: NegotiationAction) -> Dict[str, Any]:
        """
        Convert action to payload format for WebSocket transmission.

        Args:
            action: The NegotiationAction to convert

        Returns:
            Dict with action data ready for JSON serialization
        """
        payload = {
            "action_type": action.action_type,
        }

        if action.offer is not None:
            payload["offer"] = action.offer

        if action.message is not None:
            payload["message"] = action.message

        return payload

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[NegotiationObservation]:
        """
        Parse server response into StepResult with typed observation.

        Args:
            payload: Raw response dict from server

        Returns:
            StepResult containing NegotiationObservation
        """
        # Extract observation data
        obs_data = payload.get("observation", payload)

        # Parse issues
        issues_raw = obs_data.get("issues", {})
        issues = {}
        for name, spec in issues_raw.items():
            if isinstance(spec, dict):
                issues[name] = IssueSpec(**spec)
            elif isinstance(spec, IssueSpec):
                issues[name] = spec

        # Parse recent offers
        recent_raw = obs_data.get("recent_offers", [])
        recent_offers = []
        for record in recent_raw:
            if isinstance(record, dict):
                recent_offers.append(OfferRecord(**record))
            elif isinstance(record, OfferRecord):
                recent_offers.append(record)

        # Build observation
        observation = NegotiationObservation(
            done=payload.get("done", obs_data.get("done", False)),
            reward=payload.get("reward", obs_data.get("reward")),
            round_number=obs_data.get("round_number", 1),
            rounds_remaining=obs_data.get("rounds_remaining", 0),
            max_rounds=obs_data.get("max_rounds", 10),
            agent_role=obs_data.get("agent_role", "buyer"),
            agent_weights=obs_data.get("agent_weights", {}),
            agent_reservation_utility=obs_data.get("agent_reservation_utility", 0.0),
            agent_aspiration_utility=obs_data.get("agent_aspiration_utility", 1.0),
            issues=issues,
            agent_last_offer=obs_data.get("agent_last_offer"),
            counterpart_last_offer=obs_data.get("counterpart_last_offer"),
            counterpart_last_action=obs_data.get("counterpart_last_action", "none"),
            agent_utility_if_accept=obs_data.get("agent_utility_if_accept"),
            agent_utility_of_last_offer=obs_data.get("agent_utility_of_last_offer"),
            total_offers_made=obs_data.get("total_offers_made", 0),
            agent_offer_count=obs_data.get("agent_offer_count", 0),
            counterpart_offer_count=obs_data.get("counterpart_offer_count", 0),
            recent_offers=recent_offers,
            message=obs_data.get("message", ""),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", obs_data.get("reward")),
            done=payload.get("done", obs_data.get("done", False)),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> NegotiationState:
        """
        Parse state response into typed NegotiationState.

        Args:
            payload: Raw state dict from server

        Returns:
            NegotiationState with full episode information
        """
        # Parse offer history
        history_raw = payload.get("offer_history", [])
        offer_history = []
        for record in history_raw:
            if isinstance(record, dict):
                offer_history.append(OfferRecord(**record))
            elif isinstance(record, OfferRecord):
                offer_history.append(record)

        # Parse grader output if present
        grader_raw = payload.get("grader")
        grader = None
        if grader_raw is not None:
            if isinstance(grader_raw, dict):
                grader = GraderOutput(**grader_raw)
            elif isinstance(grader_raw, GraderOutput):
                grader = grader_raw

        return NegotiationState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            counterpart_strategy=payload.get("counterpart_strategy", ""),
            counterpart_weights=payload.get("counterpart_weights", {}),
            counterpart_reservation_utility=payload.get("counterpart_reservation_utility", 0.0),
            counterpart_aspiration_utility=payload.get("counterpart_aspiration_utility", 0.0),
            agent_role=payload.get("agent_role", ""),
            agent_weights=payload.get("agent_weights", {}),
            agent_reservation_utility=payload.get("agent_reservation_utility", 0.0),
            agent_aspiration_utility=payload.get("agent_aspiration_utility", 0.0),
            max_rounds=payload.get("max_rounds", 10),
            seed=payload.get("seed"),
            offer_history=offer_history,
            deal_reached=payload.get("deal_reached", False),
            terminal_reason=payload.get("terminal_reason"),
            grader=grader,
            last_reward_breakdown=payload.get("last_reward_breakdown", {}),
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def make_offer(
    price: float = 0.5,
    quantity: float = 0.5,
    delivery_days: float = 0.5,
    warranty_months: float = 0.5,
    payment_terms: float = 0.5,
    message: Optional[str] = None,
) -> NegotiationAction:
    """
    Convenience function to create an offer action.

    Args:
        price: Price value [0, 1] (0=lowest, 1=highest)
        quantity: Quantity value [0, 1] (0=lowest, 1=highest)
        delivery_days: Delivery timeline [0, 1] (0=fastest, 1=slowest)
        warranty_months: Warranty duration [0, 1] (0=none, 1=longest)
        payment_terms: Payment schedule [0, 1] (0=upfront, 1=installments)
        message: Optional message with the offer

    Returns:
        NegotiationAction configured as an offer
    """
    return NegotiationAction(
        action_type="offer",
        offer={
            "price": max(0.0, min(1.0, price)),
            "quantity": max(0.0, min(1.0, quantity)),
            "delivery_days": max(0.0, min(1.0, delivery_days)),
            "warranty_months": max(0.0, min(1.0, warranty_months)),
            "payment_terms": max(0.0, min(1.0, payment_terms)),
        },
        message=message,
    )


def accept_offer(message: Optional[str] = None) -> NegotiationAction:
    """
    Create an accept action.

    Args:
        message: Optional message with the acceptance

    Returns:
        NegotiationAction configured to accept counterpart's offer
    """
    return NegotiationAction(
        action_type="accept",
        offer=None,
        message=message,
    )


def reject_offer(message: Optional[str] = None) -> NegotiationAction:
    """
    Create a reject action (walks away from negotiation).

    Args:
        message: Optional message explaining rejection

    Returns:
        NegotiationAction configured to reject and end negotiation
    """
    return NegotiationAction(
        action_type="reject",
        offer=None,
        message=message,
    )
