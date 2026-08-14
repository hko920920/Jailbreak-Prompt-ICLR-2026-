import pytest

from jbspan.neutralization import DeleteNeutralizer, PlaceholderNeutralizer
from jbspan.schemas import TextSpan


def test_delete_neutralizer() -> None:
    text = "keep remove keep"
    span = TextSpan(5, 11)
    assert DeleteNeutralizer().apply(text, (span,)) == "keep  keep"


def test_placeholder_neutralizer() -> None:
    text = "abc xyz"
    span = TextSpan(4, 7)
    edited = PlaceholderNeutralizer(placeholder="[N]").apply(text, (span,))
    assert edited == "abc [N]"


def test_overlapping_spans_rejected() -> None:
    text = "abcdef"
    with pytest.raises(ValueError):
        DeleteNeutralizer().apply(text, (TextSpan(0, 3), TextSpan(2, 5)))
