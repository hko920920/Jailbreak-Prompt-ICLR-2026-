from jbspan.metrics import query_reduction, span_fraction, span_iou
from jbspan.schemas import TextSpan


def test_span_iou() -> None:
    assert span_iou((TextSpan(0, 4),), (TextSpan(2, 6),)) == 2 / 6


def test_span_fraction() -> None:
    assert span_fraction((TextSpan(0, 2), TextSpan(4, 6)), "abcdefgh") == 0.5


def test_query_reduction() -> None:
    assert query_reduction(100, 20) == 5.0
