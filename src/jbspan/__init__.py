"""Core package for causal jailbreak-span localization."""

from jbspan.schemas import (
    BehaviorScores,
    InterventionRecord,
    LocalizationResult,
    LocalizationStatus,
    PromptPair,
    TextSpan,
)

__all__ = [
    "BehaviorScores",
    "InterventionRecord",
    "LocalizationResult",
    "LocalizationStatus",
    "PromptPair",
    "TextSpan",
]

__version__ = "0.1.0"
