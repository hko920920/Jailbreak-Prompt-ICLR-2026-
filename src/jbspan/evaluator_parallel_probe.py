from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any


def deterministic_score(seed: str, record_id: str) -> str:
    return hashlib.sha256(f"{seed}|{record_id}".encode()).hexdigest()


def select_parallel_probe(
    rows: Sequence[Mapping[str, Any]],
    *,
    seed: str,
    stress_records: int,
    hash_ranked_records: int,
) -> list[dict[str, Any]]:
    """Select long-context stress cases plus an independent deterministic remainder."""
    if stress_records < 1 or hash_ranked_records < 1:
        raise ValueError("both probe strata must be non-empty")
    record_ids = [str(row["record_id"]) for row in rows]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("parallel-probe candidates contain duplicate record IDs")
    if stress_records + hash_ranked_records > len(rows):
        raise ValueError("parallel-probe request exceeds the candidate denominator")

    normalized: list[dict[str, Any]] = []
    for row in rows:
        value = dict(row)
        input_tokens = value.get("input_tokens")
        output_tokens = value.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            raise ValueError("parallel-probe candidates require integer token counts")
        value["combined_observed_tokens"] = input_tokens + output_tokens
        normalized.append(value)

    stress = sorted(
        normalized,
        key=lambda row: (-int(row["combined_observed_tokens"]), str(row["record_id"])),
    )[:stress_records]
    stress_ids = {str(row["record_id"]) for row in stress}
    remainder = sorted(
        (row for row in normalized if str(row["record_id"]) not in stress_ids),
        key=lambda row: (deterministic_score(seed, str(row["record_id"])), str(row["record_id"])),
    )[:hash_ranked_records]

    selected: list[dict[str, Any]] = []
    for selection_order, (stratum, row) in enumerate(
        [("LONGEST_OBSERVED", row) for row in stress]
        + [("DETERMINISTIC_REMAINDER", row) for row in remainder]
    ):
        value = dict(row)
        value["selection_order"] = selection_order
        value["selection_stratum"] = stratum
        value["selection_score"] = deterministic_score(seed, str(row["record_id"]))
        selected.append(value)
    return selected


def exact_output_matches(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> dict[str, bool]:
    return {
        "input_sha256": actual.get("input_sha256") == expected.get("input_sha256"),
        "input_tokens": actual.get("input_tokens") == expected.get("input_tokens"),
        "output_sha256": actual.get("output_sha256") == expected.get("output_sha256"),
        "output_characters": actual.get("output_characters")
        == expected.get("output_characters"),
        "output_tokens": actual.get("output_tokens") == expected.get("output_tokens"),
        "label": actual.get("label") == expected.get("label"),
        "label_match_count": actual.get("label_match_count")
        == expected.get("label_match_count"),
        "output_limit_stop": actual.get("output_limit_stop")
        == expected.get("output_limit_stop"),
    }
