"""Synthetic-only tests for the exact common-order audit; no study data reads."""

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "pa_common_order", Path(__file__).parents[1] / "scripts/audit_pa_common_order_v1.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def independent_error(matrix):
    width = len(matrix[0])
    optimum = width * len(matrix)
    for order in itertools.permutations(range(width)):
        rank = {mask: index for index, mask in enumerate(order)}
        total = 0
        for row in matrix:
            total += min(
                sum(
                    value is not None and value != int(rank[mask] >= split)
                    for mask, value in enumerate(row)
                )
                for split in range(width + 1)
            )
        optimum = min(optimum, total)
    return optimum


def test_nested_rows_and_constant_extremes_fit_exactly():
    matrix = ((0, 0, 0), (1, 0, 0), (1, 0, 1), (1, 1, 1))
    result = audit.analyze(matrix)
    assert result["known_fit"]["minimum_label_error_count"] == 0
    assert result["observed_crossovers"]["strict_crossover_count"] == 0
    assert result["known_fit"]["orders_evaluated"] == 6


def test_two_by_two_crossover_needs_one_label_change():
    result = audit.analyze(((1, 0), (0, 1)))
    assert result["known_fit"]["minimum_label_error_count"] == 1
    assert result["observed_crossovers"]["strict_crossover_count"] == 1
    assert result["unknown_sensitivity"]["full_table_reoptimized_error_bounds"] == [1, 1]
    assert result["known_table_common_order_incompatible"]
    assert not result["statistical_rejection_claimed"]


def test_unknown_does_not_manufacture_an_observed_crossover():
    result = audit.analyze(((1, 0), (0, None)))
    assert result["observed_crossovers"]["strict_crossover_count"] == 0
    assert result["known_fit"]["minimum_label_error_count"] == 0
    assert result["unknown_sensitivity"]["full_table_reoptimized_error_bounds"] == [0, 1]
    assert not result["known_table_common_order_incompatible"]


def test_partial_three_cycle_can_conflict_without_observed_two_by_two():
    matrix = ((1, 0, None), (None, 1, 0), (0, None, 1))
    result = audit.analyze(matrix)
    assert result["observed_crossovers"]["strict_crossover_count"] == 0
    assert result["known_fit"]["minimum_label_error_count"] == 1
    assert result["known_table_common_order_incompatible"]


def test_all_two_by_two_partial_tables_match_independent_brute_force():
    for flattened in itertools.product((0, 1, None), repeat=4):
        matrix = (flattened[:2], flattened[2:])
        result = audit.analyze(matrix)
        assert result["known_fit"]["minimum_label_error_count"] == independent_error(matrix)
        unknown = [index for index, value in enumerate(flattened) if value is None]
        errors = []
        for assignment in itertools.product((0, 1), repeat=len(unknown)):
            completed = list(flattened)
            for index, value in zip(unknown, assignment, strict=True):
                completed[index] = value
            errors.append(independent_error((completed[:2], completed[2:])))
        assert result["unknown_sensitivity"]["full_table_reoptimized_error_bounds"] == [
            min(errors), max(errors)
        ]


def test_all_three_column_complete_pairs_match_independent_brute_force():
    for flattened in itertools.product((0, 1), repeat=6):
        matrix = (flattened[:3], flattened[3:])
        result = audit.common_order_fit(matrix)
        assert result["minimum_label_error_count"] == independent_error(matrix)


def test_relabeling_rows_and_columns_preserves_error_and_witness_count():
    matrix = ((1, 0, 1), (0, 1, None), (1, 1, 0))
    expected = audit.analyze(matrix)
    for order in itertools.permutations(range(3)):
        changed = tuple(tuple(row[index] for index in order) for row in reversed(matrix))
        actual = audit.analyze(changed)
        assert actual["known_fit"]["minimum_label_error_count"] == expected["known_fit"][
            "minimum_label_error_count"
        ]
        assert actual["observed_crossovers"]["strict_crossover_count"] == expected[
            "observed_crossovers"
        ]["strict_crossover_count"]
        assert actual["unknown_sensitivity"]["full_table_reoptimized_error_bounds"] == expected[
            "unknown_sensitivity"
        ]["full_table_reoptimized_error_bounds"]


def test_witness_multiplicity_does_not_imply_independent_label_distance():
    result = audit.analyze(((1, 0), (0, 1), (0, 1), (0, 1)))
    assert result["observed_crossovers"]["strict_crossover_count"] == 3
    assert result["known_fit"]["minimum_label_error_count"] == 1
    assert max(
        cell["witness_count"] for cell in result["observed_crossovers"]["cell_witness_multiplicity"]
    ) == 3


def test_arbitrary_score_does_not_assume_subset_monotonicity():
    result = audit.analyze(((0, 1, 0, 0), (0, 1, 1, 0)))
    assert result["known_fit"]["minimum_label_error_count"] == 0


def test_eight_column_search_visits_all_orders_even_if_zero_error():
    result = audit.common_order_fit(((0, 0, 0, 0, 1, 1, 1, 1),))
    assert result["orders_evaluated"] == 40320
    assert result["optimal_order_count"] == 24 * 24
    assert result["minimum_label_error_count"] == 0


@pytest.mark.parametrize(
    "matrix",
    [(), ((0,), (0, 1)), ((True, 0),), ((0.0, 1),), ((2, 1),), (("0", 1),),
     (tuple(0 for _ in range(9)),)],
)
def test_rejects_bad_matrix(matrix):
    with pytest.raises(ValueError):
        audit.analyze(matrix)


def test_completion_bound_and_all_unknown_rows():
    with pytest.raises(ValueError, match="bounded"):
        audit.analyze(((None,) * 5, (None,) * 5))
    result = audit.analyze(((None, None),))
    assert result["known_cell_count"] == 0
    assert result["unknown_sensitivity"]["full_table_reoptimized_error_bounds"] == [0, 0]


def test_hash_mismatch_and_byte_limit_fail_before_json_parse(tmp_path, monkeypatch):
    source = tmp_path / audit.SOURCE
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not JSON and not a source artifact")
    with pytest.raises(ValueError, match="hash mismatch"):
        audit.read_source(tmp_path)
    monkeypatch.setattr(audit, "MAX_SOURCE_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound"):
        audit.read_source(tmp_path)


def synthetic_source():
    rows = []
    for index in range(9):
        values = [0, None if index < 2 else 0, 0, 1, 0, 1, 0, 1]
        rows.append({
            "instance_id": hashlib.sha256(f"instance-{index}".encode()).hexdigest(),
            "payload_sha256": hashlib.sha256(f"payload-{index}".encode()).hexdigest(),
            "truth_vector_mask_order": values,
            "original_status_mask_order": [
                "ABSTAINED" if value is None else "RECOVERED" if value else "NOT_RECOVERED"
                for value in values
            ],
            "extra_untrusted_field": "must not be copied",
        })
    return {"schema_version": audit.SOURCE_SCHEMA, "per_instance": rows}


def install_synthetic_source(tmp_path, monkeypatch, source):
    path = tmp_path / audit.SOURCE
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(source).encode()
    path.write_bytes(raw)
    monkeypatch.setattr(audit, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest())


def test_projection_excludes_untrusted_source_fields(tmp_path, monkeypatch):
    install_synthetic_source(tmp_path, monkeypatch, synthetic_source())
    rows, metadata = audit.read_source(tmp_path)
    assert len(rows) == 9
    assert all("extra_untrusted_field" not in row for row in rows)
    assert metadata["sha256"] == audit.SOURCE_SHA256


@pytest.mark.parametrize("mutation", ["duplicate", "unsafe_id", "status", "rows", "width"])
def test_source_schema_and_label_contract_fail_closed(tmp_path, monkeypatch, mutation):
    source = synthetic_source()
    if mutation == "duplicate":
        source["per_instance"][1]["instance_id"] = source["per_instance"][0]["instance_id"]
    elif mutation == "unsafe_id":
        source["per_instance"][0]["payload_sha256"] = "not a safe hash"
    elif mutation == "status":
        source["per_instance"][0]["original_status_mask_order"][0] = "RECOVERED"
    elif mutation == "rows":
        source["per_instance"].pop()
    else:
        source["per_instance"][0]["truth_vector_mask_order"].pop()
    install_synthetic_source(tmp_path, monkeypatch, source)
    with pytest.raises(ValueError):
        audit.read_source(tmp_path)


def test_path_containment_and_write_once(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        audit.contained_path(tmp_path, "../outside.safe.json")
    path = tmp_path / "new" / "safe.json"
    audit.write_once(path, {"test_count": 1})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        audit.write_once(path, {"test_count": 2})
    assert path.read_bytes() == before
