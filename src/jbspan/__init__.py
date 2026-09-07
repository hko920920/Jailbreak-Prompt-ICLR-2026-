"""Core package for payload-preserving jailbreak recovery-topology analysis."""

from jbspan.schemas import (
    BehaviorScores,
    InterventionRecord,
    LocalizationResult,
    LocalizationStatus,
    PromptPair,
    TextSpan,
)
from jbspan.topology import (
    AttackUnit,
    BehaviorOutcome,
    ExactTopologyResult,
    ImmutablePayload,
    RecoveryPolicy,
    TopologyInstance,
    evaluate_exact_topology,
)

__all__ = [
    "BehaviorScores",
    "BehaviorOutcome",
    "AttackUnit",
    "ExactTopologyResult",
    "ImmutablePayload",
    "InterventionRecord",
    "LocalizationResult",
    "LocalizationStatus",
    "PromptPair",
    "RecoveryPolicy",
    "TextSpan",
    "TopologyInstance",
    "evaluate_exact_topology",
]

__version__ = "0.1.0"
