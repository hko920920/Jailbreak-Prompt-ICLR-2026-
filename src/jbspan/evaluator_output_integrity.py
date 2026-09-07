from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

JsonObject = dict[str, Any]


def effective_output_limit_stop(row: Mapping[str, Any], *, maximum_output_tokens: int) -> bool:
    """Derive a conservative output-limit stop from server metadata.

    Some llama.cpp completion responses have reported ``stopped_limit=false``
    even when ``tokens_predicted`` equals ``n_predict``.  The token boundary is
    therefore treated as an additional, metadata-only limit-stop signal.
    """
    if maximum_output_tokens <= 0:
        raise ValueError("maximum_output_tokens must be positive")
    raw_flag = row.get("output_limit_stop")
    if not isinstance(raw_flag, bool):
        raise ValueError("output_limit_stop must be boolean")
    output_tokens = row.get("output_tokens")
    reached_boundary = (
        isinstance(output_tokens, int)
        and not isinstance(output_tokens, bool)
        and output_tokens >= maximum_output_tokens
    )
    return raw_flag or reached_boundary


def output_limit_integrity_summary(
    rows: Sequence[Mapping[str, Any]], *, maximum_output_tokens: int
) -> JsonObject:
    if not rows:
        raise ValueError("output-limit integrity summary requires records")
    record_ids = [str(row["record_id"]) for row in rows]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("output-limit integrity records contain duplicate IDs")

    raw_flag_ids: list[str] = []
    token_boundary_ids: list[str] = []
    derived_only_ids: list[str] = []
    effective_ids: list[str] = []
    missing_token_ids: list[str] = []
    for row, record_id in zip(rows, record_ids, strict=True):
        raw_flag = row.get("output_limit_stop")
        if not isinstance(raw_flag, bool):
            raise ValueError("output_limit_stop must be boolean")
        output_tokens = row.get("output_tokens")
        token_is_integer = isinstance(output_tokens, int) and not isinstance(output_tokens, bool)
        if token_is_integer:
            output_token_count = cast(int, output_tokens)
            at_boundary = output_token_count >= maximum_output_tokens
        else:
            missing_token_ids.append(record_id)
            at_boundary = False
        effective = effective_output_limit_stop(
            row, maximum_output_tokens=maximum_output_tokens
        )
        if raw_flag:
            raw_flag_ids.append(record_id)
        if at_boundary:
            token_boundary_ids.append(record_id)
        if at_boundary and not raw_flag:
            derived_only_ids.append(record_id)
        if effective:
            effective_ids.append(record_id)

    return {
        "rule": "raw_output_limit_stop OR integer_output_tokens_greater_than_or_equal_to_maximum",
        "maximum_output_tokens": maximum_output_tokens,
        "records": len(rows),
        "raw_flag_count": len(raw_flag_ids),
        "token_boundary_count": len(token_boundary_ids),
        "derived_only_count": len(derived_only_ids),
        "effective_count": len(effective_ids),
        "effective_fraction": len(effective_ids) / len(rows),
        "missing_output_token_count": len(missing_token_ids),
        "raw_flag_record_ids": sorted(raw_flag_ids),
        "token_boundary_record_ids": sorted(token_boundary_ids),
        "derived_only_record_ids": sorted(derived_only_ids),
        "effective_record_ids": sorted(effective_ids),
        "missing_output_token_record_ids": sorted(missing_token_ids),
    }
