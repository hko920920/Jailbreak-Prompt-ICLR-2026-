from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True, order=True)
class TextSpan:
    """Half-open character span [start, end)."""

    start: int
    end: int
    label: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("span start must be non-negative")
        if self.end <= self.start:
            raise ValueError("span end must be greater than span start")

    @property
    def length(self) -> int:
        return self.end - self.start

    def text(self, source: str) -> str:
        if self.end > len(source):
            raise ValueError("span exceeds source length")
        return source[self.start : self.end]

    def overlaps(self, other: TextSpan) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class PromptPair:
    id: str
    behavior: str
    original_prompt: str
    jailbreak_prompt: str
    attack_family: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("id must be non-empty")
        if not self.original_prompt.strip():
            raise ValueError("original_prompt must be non-empty")
        if not self.jailbreak_prompt.strip():
            raise ValueError("jailbreak_prompt must be non-empty")


@dataclass(frozen=True)
class BehaviorScores:
    refusal: float
    harmful_compliance: float
    intent_preservation: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("refusal", self.refusal),
            ("harmful_compliance", self.harmful_compliance),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.intent_preservation is not None and not 0.0 <= self.intent_preservation <= 1.0:
            raise ValueError("intent_preservation must be in [0, 1]")


@dataclass(frozen=True)
class InterventionRecord:
    example_id: str
    spans: tuple[TextSpan, ...]
    neutralizer: str
    seed: int
    edited_prompt: str
    response: str
    scores: BehaviorScores
    target_queries: int = 1


class LocalizationStatus(str, Enum):
    LOCALIZED = "LOCALIZED"
    ABSTAIN_DISTRIBUTED = "ABSTAIN_DISTRIBUTED"
    BASELINE_ATTACK_FAILED = "BASELINE_ATTACK_FAILED"
    ORIGINAL_NOT_REFUSED = "ORIGINAL_NOT_REFUSED"
    INTENT_NOT_PRESERVED = "INTENT_NOT_PRESERVED"
    QUERY_BUDGET_EXHAUSTED = "QUERY_BUDGET_EXHAUSTED"


@dataclass(frozen=True)
class LocalizationResult:
    example_id: str
    status: LocalizationStatus
    spans: tuple[TextSpan, ...] = ()
    refusal_effect: float = 0.0
    harmful_compliance_effect: float = 0.0
    intent_preservation: float | None = None
    cost: float | None = None
    query_count: int = 0
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload
