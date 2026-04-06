"""
NegotiationEnv - A Multi-Issue Bilateral Negotiation RL Environment

Built on the OpenEnv framework for LLM post-training with GRPO.
"""

from models import (
    NegotiationAction,
    NegotiationObservation,
    NegotiationState,
    IssueSpec,
    OfferRecord,
    GraderOutput,
)
from client import NegotiationEnv

__all__ = [
    "NegotiationAction",
    "NegotiationObservation",
    "NegotiationState",
    "NegotiationEnv",
    "IssueSpec",
    "OfferRecord",
    "GraderOutput",
]

__version__ = "1.0.0"

# Grader functions (imported for openenv.yaml fn references)
from graders import grade_easy_conceder, grade_medium_tft, grade_hard_hardliner

__all__ += [
    "grade_easy_conceder",
    "grade_medium_tft",
    "grade_hard_hardliner",
]
