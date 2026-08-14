from __future__ import annotations

from typing import Protocol

from jbspan.schemas import BehaviorScores, PromptPair


class TargetModel(Protocol):
    name: str

    def generate(self, prompt: str, *, seed: int) -> str: ...


class ResponseJudge(Protocol):
    name: str

    def score(self, pair: PromptPair, prompt: str, response: str) -> BehaviorScores: ...


class IntentJudge(Protocol):
    name: str

    def score(self, pair: PromptPair, edited_prompt: str) -> float: ...
