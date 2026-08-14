from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jbspan.schemas import TextSpan


class Neutralizer(Protocol):
    name: str

    def apply(self, text: str, spans: tuple[TextSpan, ...]) -> str: ...


def validate_spans(text: str, spans: tuple[TextSpan, ...]) -> tuple[TextSpan, ...]:
    ordered = tuple(sorted(spans))
    for span in ordered:
        if span.end > len(text):
            raise ValueError("span exceeds text length")
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left.overlaps(right):
            raise ValueError("neutralization spans must not overlap")
    return ordered


def replace_spans(text: str, spans: tuple[TextSpan, ...], replacements: tuple[str, ...]) -> str:
    ordered = validate_spans(text, spans)
    if len(ordered) != len(replacements):
        raise ValueError("one replacement is required per span")

    chunks: list[str] = []
    cursor = 0
    for span, replacement in zip(ordered, replacements, strict=True):
        chunks.append(text[cursor : span.start])
        chunks.append(replacement)
        cursor = span.end
    chunks.append(text[cursor:])
    return "".join(chunks)


@dataclass(frozen=True)
class DeleteNeutralizer:
    name: str = "delete"

    def apply(self, text: str, spans: tuple[TextSpan, ...]) -> str:
        return replace_spans(text, spans, tuple("" for _ in spans))


@dataclass(frozen=True)
class PlaceholderNeutralizer:
    placeholder: str = " [neutral context] "
    name: str = "placeholder"

    def apply(self, text: str, spans: tuple[TextSpan, ...]) -> str:
        return replace_spans(text, spans, tuple(self.placeholder for _ in spans))


@dataclass(frozen=True)
class LengthAwareNeutralizer:
    token: str = "context"
    name: str = "length_aware"

    def apply(self, text: str, spans: tuple[TextSpan, ...]) -> str:
        replacements: list[str] = []
        for span in spans:
            original = span.text(text)
            word_count = max(1, len(original.split()))
            replacements.append(" " + " ".join([self.token] * word_count) + " ")
        return replace_spans(text, spans, tuple(replacements))
