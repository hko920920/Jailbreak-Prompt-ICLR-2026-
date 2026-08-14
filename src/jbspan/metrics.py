from __future__ import annotations

from jbspan.schemas import TextSpan


def covered_characters(spans: tuple[TextSpan, ...]) -> int:
    if not spans:
        return 0
    ordered = sorted(spans)
    total = 0
    current_start, current_end = ordered[0].start, ordered[0].end
    for span in ordered[1:]:
        if span.start <= current_end:
            current_end = max(current_end, span.end)
        else:
            total += current_end - current_start
            current_start, current_end = span.start, span.end
    return total + current_end - current_start


def span_iou(predicted: tuple[TextSpan, ...], reference: tuple[TextSpan, ...]) -> float:
    if not predicted and not reference:
        return 1.0
    pred_points = _points(predicted)
    ref_points = _points(reference)
    union = pred_points | ref_points
    if not union:
        return 0.0
    return len(pred_points & ref_points) / len(union)


def span_fraction(spans: tuple[TextSpan, ...], prompt: str) -> float:
    if not prompt:
        raise ValueError("prompt must be non-empty")
    return covered_characters(spans) / len(prompt)


def query_reduction(exhaustive_queries: int, method_queries: int) -> float:
    if method_queries <= 0:
        raise ValueError("method_queries must be positive")
    return exhaustive_queries / method_queries


def _points(spans: tuple[TextSpan, ...]) -> set[int]:
    points: set[int] = set()
    for span in spans:
        points.update(range(span.start, span.end))
    return points
