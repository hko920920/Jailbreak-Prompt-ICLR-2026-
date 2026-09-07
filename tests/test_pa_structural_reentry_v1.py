"""Synthetic-only tests; never read or modify original study artifacts."""

import importlib.util
import itertools
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "pa_structural_reentry", Path(__file__).parents[1] / "scripts/audit_pa_structural_reentry_v1.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_complete_profiles_and_fixed_macro_are_different_questions():
    first = audit.characterize((0, 1, 0, 1, 0, 1, 0, 1))
    second = audit.characterize((0, 0, 0, 1, 0, 0, 0, 1))
    assert first["fixed_macro_status"] == second["fixed_macro_status"] == 1
    assert first["coarse_truth_vector"] == second["coarse_truth_vector"] == [0, 1, 0, 1]
    assert first["fixed_macro_strict_minimality"] == "CERTIFIED_NOT_MINIMAL"
    assert second["fixed_macro_strict_minimality"] == "CERTIFIED_MINIMAL"
    pair = audit.compare(first, second)
    assert pair["known_decision_contradiction_masks"] == [1, 5]
    assert pair["families_certified_different"]


def test_unknown_is_not_negative_or_a_different_family_certificate():
    partial = audit.characterize((0, None, 0, 1, 0, 1, 0, 1))
    singleton = audit.characterize((0, 1, 0, 1, 0, 1, 0, 1))
    assert partial["necessary_strict_minimum_masks"] == []
    assert partial["possible_strict_minimum_masks"] == [1, 3, 5]
    assert partial["compatible_strict_minimal_families"] == [[1], [3, 5]]
    assert partial["minimum_recovery_cardinality_completion_bounds"] == [1, 2]
    assert partial["fixed_macro_strict_minimality"] == "UNRESOLVED"
    result = audit.compare(partial, singleton)
    assert not result["truth_vectors_certified_different"]
    assert result["truth_vectors_equality_unresolved"]
    assert result["family_equality_unresolved"]


def test_nonmonotone_truth_difference_does_not_imply_different_minimal_family():
    first = audit.characterize((0, 1, 0, 0), macro=1)
    second = audit.characterize((0, 1, 0, 1), macro=1)
    result = audit.compare(first, second)
    assert result["truth_vectors_certified_different"]
    assert result["families_certified_equal"]


def test_nonmonotone_strict_minima_checks_all_strict_subsets():
    result = audit.characterize((0, 1, 0, 0, 0, 0, 0, 1))
    assert result["necessary_strict_minimum_masks"] == [1]
    assert result["fixed_macro_status"] == 0


def test_every_two_unit_partial_table_against_independent_set_enumeration():
    for values in itertools.product((0, 1, None), repeat=4):
        result = audit.characterize(values, macro=3)
        families = []
        for completed in itertools.product((0, 1), repeat=4):
            if any(
                value is not None and value != bit
                for value, bit in zip(values, completed, strict=True)
            ):
                continue
            positives = [
                frozenset(i for i in range(2) if mask & (1 << i))
                for mask, bit in enumerate(completed)
                if bit
            ]
            family = {
                sum(1 << i for i in subset)
                for subset in positives
                if not any(other < subset for other in positives)
            }
            families.append(family)
        expected_lower = set(families[0]).intersection(*families[1:])
        expected_upper = set().union(*families)
        assert set(result["necessary_strict_minimum_masks"]) == expected_lower
        assert set(result["possible_strict_minimum_masks"]) == expected_upper


def test_pairwise_partition_and_repeated_payload_rejection():
    first = {
        "instance_id": "a",
        "payload_sha256": "p1",
        **audit.characterize((0, 1, 0, 1, 0, 1, 0, 1)),
    }
    second = {
        "instance_id": "b",
        "payload_sha256": "p2",
        **audit.characterize((0, None, 0, 1, 0, 1, 0, 1)),
    }
    result = audit.summarize([first, second])
    assert result["pairwise"]["pair_count"] == 1
    assert result["pairwise"]["truth_vectors_equality_unresolved"] == 1
    assert result["fixed_existing_macro_baseline"]["recovery_successes"] == 2
    assert result["fixed_existing_macro_baseline"]["oracle_unit_saving_completion_bounds"] == [1, 2]
    with pytest.raises(ValueError, match="distinct"):
        audit.summarize([first, first])


@pytest.mark.parametrize("values", [(), (0, 1, 0), (0, 2, 0, 1), (0,) * 16])
def test_invalid_vector_fails_closed(values):
    with pytest.raises(ValueError):
        audit.characterize(values)


def test_invalid_macro_fails_closed():
    with pytest.raises(ValueError, match="macro"):
        audit.characterize((0, 0, 0, 1), macro=4)


def synthetic_item():
    values = (0, 0, 0, 1, 0, 0, 0, 1)
    return {
        "instance_id": "synthetic-instance",
        "payload_sha256": "synthetic-payload-not-a-real-study-record",
        "unit_ids": list(audit.UNITS),
        "minimal_sets": [[audit.UNITS[0], audit.UNITS[1]]],
        "subset_decisions": [
            {
                "selected_unit_ids": [
                    unit for i, unit in enumerate(audit.UNITS) if mask & (1 << i)
                ],
                "status": "RECOVERED" if value else "NOT_RECOVERED",
            }
            for mask, value in enumerate(values)
        ],
    }


def test_synthetic_extraction_reconstructs_mask_not_input_row_order():
    item = synthetic_item()
    item["subset_decisions"].reverse()
    result = audit.extract(item)
    assert result["truth_vector_mask_order"] == [0, 0, 0, 1, 0, 0, 0, 1]
    assert result["necessary_strict_minimum_masks"] == [3]


@pytest.mark.parametrize("problem", ["missing", "duplicate", "bad_status", "bad_minimum"])
def test_synthetic_extraction_rejects_invalid_input(problem):
    item = synthetic_item()
    if problem == "missing":
        item["subset_decisions"].pop()
    elif problem == "duplicate":
        item["subset_decisions"].append(item["subset_decisions"][0])
    elif problem == "bad_status":
        item["subset_decisions"][0]["status"] = "SAFE_ASSUMED"
    else:
        item["minimal_sets"] = [[audit.UNITS[0]]]
    with pytest.raises(ValueError):
        audit.extract(item)
