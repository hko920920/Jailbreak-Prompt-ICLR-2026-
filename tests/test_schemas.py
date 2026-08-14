import pytest

from jbspan.schemas import TextSpan


def test_text_span_is_half_open() -> None:
    span = TextSpan(1, 4)
    assert span.length == 3
    assert span.text("abcde") == "bcd"


def test_invalid_span_rejected() -> None:
    with pytest.raises(ValueError):
        TextSpan(2, 2)
