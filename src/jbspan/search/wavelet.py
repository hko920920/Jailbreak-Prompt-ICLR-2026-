from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

from jbspan.schemas import LocalizationResult, LocalizationStatus, PromptPair
from jbspan.scoring import AggregateEffect, CausalEvaluator
from jbspan.search.common import SearchConfig, span_cost
from jbspan.segmentation import SpanNode


@dataclass(frozen=True)
class NodeSignal:
    effect: AggregateEffect
    haar_detail: float = 0.0
    interaction_residual: float = 0.0


@dataclass(frozen=True)
class WaveletTreeSearch:
    """Adaptive interval search using tree-Haar contrasts as query priorities.

    The coefficients are proposal signals only. Final outputs are always directly
    verified by the causal evaluator.
    """

    name: str = "wavelet_tree"

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

        evaluated: dict[tuple[int, int], NodeSignal] = {}
        queue: list[tuple[float, int, SpanNode]] = [(0.0, tree.span.start, tree)]
        best: tuple[float, SpanNode, AggregateEffect] | None = None

        while queue and evaluator.query_count - start_queries < config.max_queries:
            _, _, node = heapq.heappop(queue)
            signal = self._get_signal(pair, node, evaluator, evaluated)
            if (
                signal.effect.refusal_effect >= config.effect_threshold
                and signal.effect.intent_preservation >= config.intent_threshold
            ):
                cost = span_cost(
                    pair.jailbreak_prompt,
                    node.span.length,
                    1,
                    config.span_set_penalty,
                )
                candidate = (cost, node, signal.effect)
                if best is None or cost < best[0]:
                    best = candidate

            if node.is_leaf:
                continue
            if evaluator.query_count - start_queries >= config.max_queries:
                break

            assert node.left is not None and node.right is not None
            left_signal = self._get_signal(pair, node.left, evaluator, evaluated)
            if evaluator.query_count - start_queries >= config.max_queries:
                break
            right_signal = self._get_signal(pair, node.right, evaluator, evaluated)

            detail = self._haar_detail(node, left_signal.effect, right_signal.effect)
            residual = max(
                0.0,
                signal.effect.refusal_effect
                - left_signal.effect.refusal_effect
                - right_signal.effect.refusal_effect,
            )
            evaluated[(node.span.start, node.span.end)] = NodeSignal(
                effect=signal.effect,
                haar_detail=detail,
                interaction_residual=residual,
            )

            self._push_child(queue, node.left, left_signal, detail, residual)
            self._push_child(queue, node.right, right_signal, -detail, residual)

        queries = evaluator.query_count - start_queries
        if best is None:
            status = (
                LocalizationStatus.QUERY_BUDGET_EXHAUSTED
                if queries >= config.max_queries
                else LocalizationStatus.ABSTAIN_DISTRIBUTED
            )
            return LocalizationResult(
                pair.id,
                status=status,
                query_count=queries,
                diagnostics={"evaluated_nodes": len(evaluated)},
            )

        cost, node, effect = best
        return LocalizationResult(
            pair.id,
            status=LocalizationStatus.LOCALIZED,
            spans=(node.span,),
            refusal_effect=effect.refusal_effect,
            harmful_compliance_effect=effect.harmful_compliance_effect,
            intent_preservation=effect.intent_preservation,
            cost=cost,
            query_count=queries,
            diagnostics={"evaluated_nodes": len(evaluated)},
        )

    @staticmethod
    def _get_signal(
        pair: PromptPair,
        node: SpanNode,
        evaluator: CausalEvaluator,
        evaluated: dict[tuple[int, int], NodeSignal],
    ) -> NodeSignal:
        key = (node.span.start, node.span.end)
        signal = evaluated.get(key)
        if signal is None:
            signal = NodeSignal(evaluator.evaluate(pair, (node.span,)))
            evaluated[key] = signal
        return signal

    @staticmethod
    def _haar_detail(
        parent: SpanNode,
        left: AggregateEffect,
        right: AggregateEffect,
    ) -> float:
        assert parent.left is not None and parent.right is not None
        left_len = parent.left.span.length
        right_len = parent.right.span.length
        normalization = math.sqrt((left_len * right_len) / (left_len + right_len))
        return normalization * (
            left.refusal_effect / left_len - right.refusal_effect / right_len
        )

    @staticmethod
    def _push_child(
        queue: list[tuple[float, int, SpanNode]],
        node: SpanNode,
        signal: NodeSignal,
        signed_detail: float,
        residual: float,
    ) -> None:
        priority = (
            signal.effect.refusal_effect
            + abs(signed_detail)
            + 0.5 * residual
            + 0.01 / max(1, node.span.length)
        )
        heapq.heappush(queue, (-priority, node.span.start, node))
