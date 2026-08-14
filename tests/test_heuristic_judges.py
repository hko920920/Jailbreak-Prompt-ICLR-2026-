from __future__ import annotations

from jbspan.adapters.heuristic import HeuristicResponseJudge, TokenRetentionIntentJudge
from jbspan.schemas import PromptPair


def _pair() -> PromptPair:
    return PromptPair(
        id="p",
        behavior="safe demo",
        original_prompt="Describe the safe demonstration task",
        jailbreak_prompt="context. trigger. Describe the safe demonstration task.",
        attack_family="toy",
    )


def test_refusal_heuristic() -> None:
    judge = HeuristicResponseJudge()
    scores = judge.score(_pair(), "prompt", "I cannot assist with that request.")
    assert scores.refusal == 1.0
    assert scores.harmful_compliance == 0.0


def test_token_retention_intent() -> None:
    judge = TokenRetentionIntentJudge()
    assert judge.score(_pair(), "Describe the safe demonstration task in detail") == 1.0
    assert judge.score(_pair(), "unrelated context") == 0.0
