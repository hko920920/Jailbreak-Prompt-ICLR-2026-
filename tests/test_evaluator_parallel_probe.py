from __future__ import annotations

from jbspan.evaluator_parallel_probe import (
    exact_output_matches,
    select_parallel_probe,
)


def candidate(record_id: str, input_tokens: int, output_tokens: int) -> dict[str, object]:
    return {
        "record_id": record_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def test_probe_selection_is_deterministic_and_keeps_longest_cases() -> None:
    rows = [candidate(f"r{index}", index * 10, index) for index in range(1, 11)]
    first = select_parallel_probe(
        rows, seed="probe", stress_records=3, hash_ranked_records=4
    )
    second = select_parallel_probe(
        list(reversed(rows)), seed="probe", stress_records=3, hash_ranked_records=4
    )
    assert first == second
    assert [row["record_id"] for row in first[:3]] == ["r10", "r9", "r8"]
    assert len(first) == 7
    assert len({row["record_id"] for row in first}) == 7


def test_exact_output_comparison_covers_content_and_parser_identity() -> None:
    expected = {
        "input_sha256": "a",
        "input_tokens": 10,
        "output_sha256": "b",
        "output_characters": 20,
        "output_tokens": 5,
        "label": 1,
        "label_match_count": 1,
        "output_limit_stop": False,
    }
    assert all(exact_output_matches(expected, expected).values())
    changed = dict(expected)
    changed["output_sha256"] = "different"
    matches = exact_output_matches(expected, changed)
    assert matches["output_sha256"] is False
    assert sum(matches.values()) == len(matches) - 1
