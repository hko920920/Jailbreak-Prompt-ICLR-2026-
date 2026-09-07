from __future__ import annotations

import pytest

from jbspan.evaluator_output_integrity import (
    effective_output_limit_stop,
    output_limit_integrity_summary,
)


@pytest.mark.parametrize(
    ("raw_flag", "tokens", "expected"),
    [
        (False, 1535, False),
        (False, 1536, True),
        (False, 1537, True),
        (True, 10, True),
    ],
)
def test_effective_output_limit_stop_uses_flag_or_token_boundary(
    raw_flag: bool, tokens: int, expected: bool
) -> None:
    assert (
        effective_output_limit_stop(
            {"output_limit_stop": raw_flag, "output_tokens": tokens},
            maximum_output_tokens=1536,
        )
        is expected
    )


def test_output_limit_integrity_summary_records_derived_only_stops() -> None:
    summary = output_limit_integrity_summary(
        [
            {"record_id": "a", "output_limit_stop": False, "output_tokens": 1536},
            {"record_id": "b", "output_limit_stop": True, "output_tokens": 100},
            {"record_id": "c", "output_limit_stop": False, "output_tokens": 42},
        ],
        maximum_output_tokens=1536,
    )
    assert summary["raw_flag_count"] == 1
    assert summary["token_boundary_count"] == 1
    assert summary["derived_only_record_ids"] == ["a"]
    assert summary["effective_count"] == 2
    assert summary["effective_fraction"] == 2 / 3


def test_output_limit_integrity_summary_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        output_limit_integrity_summary(
            [
                {"record_id": "a", "output_limit_stop": False, "output_tokens": 1},
                {"record_id": "a", "output_limit_stop": False, "output_tokens": 2},
            ],
            maximum_output_tokens=3,
        )
