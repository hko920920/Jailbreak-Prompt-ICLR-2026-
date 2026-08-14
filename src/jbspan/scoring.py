from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean

from jbspan.adapters.base import IntentJudge, ResponseJudge, TargetModel
from jbspan.neutralization import Neutralizer
from jbspan.schemas import BehaviorScores, InterventionRecord, PromptPair, TextSpan


@dataclass(frozen=True)
class AggregateEffect:
    refusal_effect: float
    harmful_compliance_effect: float
    intent_preservation: float
    records: tuple[InterventionRecord, ...]


@dataclass
class CausalEvaluator:
    target: TargetModel
    response_judge: ResponseJudge
    intent_judge: IntentJudge
    neutralizers: tuple[Neutralizer, ...]
    seeds: tuple[int, ...] = (0,)
    _baseline_cache: dict[str, BehaviorScores] = field(default_factory=dict, init=False)
    query_count: int = field(default=0, init=False)

    def baseline(self, pair: PromptPair) -> BehaviorScores:
        cached = self._baseline_cache.get(pair.id)
        if cached is not None:
            return cached
        scores = self._mean_scores(pair, pair.jailbreak_prompt)
        self._baseline_cache[pair.id] = scores
        return scores

    def evaluate(self, pair: PromptPair, spans: tuple[TextSpan, ...]) -> AggregateEffect:
        if not spans:
            raise ValueError("at least one intervention span is required")
        baseline = self.baseline(pair)
        records: list[InterventionRecord] = []
        intent_scores: list[float] = []

        for neutralizer in self.neutralizers:
            edited_prompt = neutralizer.apply(pair.jailbreak_prompt, spans)
            intent = self.intent_judge.score(pair, edited_prompt)
            intent_scores.append(intent)
            for seed in self.seeds:
                response = self.target.generate(edited_prompt, seed=seed)
                self.query_count += 1
                judged = self.response_judge.score(pair, edited_prompt, response)
                scores = BehaviorScores(
                    refusal=judged.refusal,
                    harmful_compliance=judged.harmful_compliance,
                    intent_preservation=intent,
                )
                records.append(
                    InterventionRecord(
                        example_id=pair.id,
                        spans=spans,
                        neutralizer=neutralizer.name,
                        seed=seed,
                        edited_prompt=edited_prompt,
                        response=response,
                        scores=scores,
                    )
                )

        return AggregateEffect(
            refusal_effect=fmean(record.scores.refusal for record in records) - baseline.refusal,
            harmful_compliance_effect=(
                baseline.harmful_compliance
                - fmean(record.scores.harmful_compliance for record in records)
            ),
            intent_preservation=fmean(intent_scores),
            records=tuple(records),
        )

    def _mean_scores(self, pair: PromptPair, prompt: str) -> BehaviorScores:
        scored: list[BehaviorScores] = []
        for seed in self.seeds:
            response = self.target.generate(prompt, seed=seed)
            self.query_count += 1
            scored.append(self.response_judge.score(pair, prompt, response))
        return BehaviorScores(
            refusal=fmean(score.refusal for score in scored),
            harmful_compliance=fmean(score.harmful_compliance for score in scored),
        )
