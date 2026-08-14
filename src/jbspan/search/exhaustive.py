from __future__ import annotations

from dataclasses import dataclass

from jbspan.schemas import LocalizationResult, LocalizationStatus, PromptPair, TextSpan
from jbspan.scoring import CausalEvaluator
from jbspan.search.common import SearchConfig, span_cost
from jbspan.segmentation import SpanNode


@dataclass(frozen=True)
class ExhaustiveAtomicSearch:
    name: str = "exhaustive_atomic"

    def localize(
        self,
        pair: PromptPair,
        tree: SpanNode,
        evaluator: CausalEvaluator,
        config: SearchConfig,
    ) -> LocalizationResult:
        start_queries = evaluator.query_count
        baseline = evaluator.baseline(pair)
        if baseline.harmful_compliance < 0.5:
            return LocalizationResult(
                example_id=pair.id,
                status=LocalizationStatus.BASELINE_ATTACK_FAILED,
                query_count=evaluator.query_count - start_queries,
            )

        best: tuple[float, TextSpan, float, float, float] | None = None
        for span in tree.leaves():
            if evaluator.query_count - start_queries >= config.max_queries:
                break
            effect = evaluator.evaluate(pair, (span,))
            if (
                effect.refusal_effect >= config.effect_threshold
                and effect.intent_preservation >= config.intent_threshold
            ):
                cost = span_cost(pair.jailbreak_prompt, span.length, 1, config.span_set_penalty)
                candidate = (
                    cost,
                    span,
                    effect.refusal_effect,
                    effect.harmful_compliance_effect,
                    effect.intent_preservation,
                )
                if best is None or candidate[0] < best[0]:
                    best = candidate

        queries = evaluator.query_count - start_queries
        if best is None:
            status = (
                LocalizationStatus.QUERY_BUDGET_EXHAUSTED
                if queries >= config.max_queries
                else LocalizationStatus.ABSTAIN_DISTRIBUTED
            )
            return LocalizationResult(pair.id, status=status, query_count=queries)

        cost, span, refusal, harmful, intent = best
        return LocalizationResult(
            example_id=pair.id,
            status=LocalizationStatus.LOCALIZED,
            spans=(span,),
            refusal_effect=refusal,
            harmful_compliance_effect=harmful,
            intent_preservation=intent,
            cost=cost,
            query_count=queries,
        )
