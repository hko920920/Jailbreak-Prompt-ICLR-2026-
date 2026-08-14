from __future__ import annotations

import heapq
from dataclasses import dataclass

from jbspan.schemas import LocalizationResult, LocalizationStatus, PromptPair
from jbspan.scoring import CausalEvaluator
from jbspan.search.common import SearchConfig, span_cost
from jbspan.segmentation import SpanNode


@dataclass(frozen=True)
class GreedyHierarchicalSearch:
    name: str = "greedy_hierarchical"

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
                pair.id,
                status=LocalizationStatus.BASELINE_ATTACK_FAILED,
                query_count=evaluator.query_count - start_queries,
            )

        queue: list[tuple[float, int, SpanNode]] = [(0.0, tree.span.start, tree)]
        best: tuple[float, SpanNode, float, float, float] | None = None

        while queue and evaluator.query_count - start_queries < config.max_queries:
            _, _, node = heapq.heappop(queue)
            effect = evaluator.evaluate(pair, (node.span,))
            causally_active = effect.refusal_effect >= config.effect_threshold
            valid = causally_active and effect.intent_preservation >= config.intent_threshold
            if valid:
                cost = span_cost(
                    pair.jailbreak_prompt,
                    node.span.length,
                    1,
                    config.span_set_penalty,
                )
                candidate = (
                    cost,
                    node,
                    effect.refusal_effect,
                    effect.harmful_compliance_effect,
                    effect.intent_preservation,
                )
                if best is None or candidate[0] < best[0]:
                    best = candidate

            # A coarse parent may destroy the requested behavior and therefore fail the
            # intent-preservation constraint even when it contains a valid smaller cause.
            # Use behavioral effect—not final validity—to decide whether to refine it.
            if causally_active and not node.is_leaf:
                assert node.left is not None and node.right is not None
                heapq.heappush(queue, (-effect.refusal_effect, node.left.span.start, node.left))
                heapq.heappush(queue, (-effect.refusal_effect, node.right.span.start, node.right))

        queries = evaluator.query_count - start_queries
        if best is None:
            status = (
                LocalizationStatus.QUERY_BUDGET_EXHAUSTED
                if queries >= config.max_queries
                else LocalizationStatus.ABSTAIN_DISTRIBUTED
            )
            return LocalizationResult(pair.id, status=status, query_count=queries)

        cost, node, refusal, harmful, intent = best
        return LocalizationResult(
            pair.id,
            status=LocalizationStatus.LOCALIZED,
            spans=(node.span,),
            refusal_effect=refusal,
            harmful_compliance_effect=harmful,
            intent_preservation=intent,
            cost=cost,
            query_count=queries,
        )
