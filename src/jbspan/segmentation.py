from __future__ import annotations

import re
from dataclasses import dataclass

from jbspan.schemas import TextSpan

_BOUNDARY_RE = re.compile(r"(?<=[.!?;:\n])\s+|\s+(?=(?:but|however|then|while|and)\b)", re.I)


@dataclass(frozen=True)
class SpanNode:
    span: TextSpan
    depth: int
    left: SpanNode | None = None
    right: SpanNode | None = None

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None

    def leaves(self) -> tuple[TextSpan, ...]:
        if self.is_leaf:
            return (self.span,)
        assert self.left is not None and self.right is not None
        return self.left.leaves() + self.right.leaves()


class RegexClauseSegmenter:
    """Deterministic clause-like segmentation with exact character offsets.

    This is an infrastructure baseline, not the final semantic segmenter.
    """

    def __init__(self, minimum_chars: int = 1) -> None:
        if minimum_chars < 1:
            raise ValueError("minimum_chars must be positive")
        self.minimum_chars = minimum_chars

    def segment(self, text: str) -> tuple[TextSpan, ...]:
        if not text:
            return ()

        spans: list[TextSpan] = []
        cursor = 0
        for match in _BOUNDARY_RE.finditer(text):
            raw_start, raw_end = cursor, match.start()
            start, end = self._trim(text, raw_start, raw_end)
            if end - start >= self.minimum_chars:
                spans.append(TextSpan(start, end, label="atomic"))
            cursor = match.end()

        start, end = self._trim(text, cursor, len(text))
        if end - start >= self.minimum_chars:
            spans.append(TextSpan(start, end, label="atomic"))

        if not spans and text.strip():
            start = len(text) - len(text.lstrip())
            end = len(text.rstrip())
            spans.append(TextSpan(start, end, label="atomic"))
        return tuple(spans)

    @staticmethod
    def _trim(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end


def build_balanced_tree(segments: tuple[TextSpan, ...]) -> SpanNode:
    if not segments:
        raise ValueError("at least one segment is required")
    for previous, current in zip(segments, segments[1:], strict=False):
        if previous.end > current.start:
            raise ValueError("segments must be sorted and non-overlapping")

    def build(start: int, end: int, depth: int) -> SpanNode:
        if end - start == 1:
            leaf = segments[start]
            return SpanNode(TextSpan(leaf.start, leaf.end, label="leaf"), depth)
        midpoint = (start + end) // 2
        left = build(start, midpoint, depth + 1)
        right = build(midpoint, end, depth + 1)
        return SpanNode(
            TextSpan(left.span.start, right.span.end, label="interval"),
            depth,
            left=left,
            right=right,
        )

    return build(0, len(segments), 0)
