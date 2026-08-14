from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jbspan.schemas import LocalizationResult, PromptPair
from jbspan.scoring import CausalEvaluator
from jbspan.segmentation import SpanNode


@dataclass(frozen=True)
class SearchConfig:
    effect_threshold: float = 0.5
    intent_threshold: float = 0.95
    max_queries: int = 100
    span_set_penalty: float = 0.05


class SearchStrategy(Protocol):
    name: str

    def localize(
        self,
        pair: PromptPair,
        tree: SpanNode,
        evaluator: CausalEvaluator,
        config: SearchConfig,
    ) -> LocalizationResult: ...


def span_cost(prompt: str, covered_chars: int, span_count: int, penalty: float) -> float:
    if not prompt:
        raise ValueError("prompt must be non-empty")
    return covered_chars / len(prompt) + penalty * max(0, span_count - 1)
