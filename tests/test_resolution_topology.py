from __future__ import annotations

import pytest

from jbspan.resolution_topology import (
    all_subsets,
    certified_minimal_family,
    contiguous_partitions,
    evaluate_partition_topology,
    set_partitions,
)


def test_partition_enumerators_match_known_bell_and_contiguous_counts() -> None:
    units = tuple(f"u{index}" for index in range(7))
    assert len(contiguous_partitions(units)) == 64
    assert len(set_partitions(units)) == 877
    assert len(contiguous_partitions(("a", "b", "c"))) == 4
    assert len(set_partitions(("a", "b", "c"))) == 5


def test_one_adjacent_merge_can_collapse_a_nonsingleton_explanation() -> None:
    units = ("a", "b", "c")
    statuses = {subset: "NOT_RECOVERED" for subset in all_subsets(units)}
    statuses[("a", "b")] = "RECOVERED"
    statuses[("a", "b", "c")] = "RECOVERED"

    fine = evaluate_partition_topology(
        units, statuses, (("a",), ("b",), ("c",))
    )
    merged_ab = evaluate_partition_topology(
        units, statuses, (("a", "b"), ("c",))
    )
    merged_bc = evaluate_partition_topology(
        units, statuses, (("a",), ("b", "c"))
    )

    assert fine.certified_atomic_sets == (("a", "b"),)
    assert fine.nontrivial is True
    assert merged_ab.certified_atomic_sets == (("a", "b"),)
    assert merged_ab.minimum_order == 1
    assert merged_ab.nontrivial is False
    assert merged_bc.certified_atomic_sets == (("a", "b", "c"),)
    assert merged_bc.minimum_order == 2
    assert merged_bc.nontrivial is True


def test_unresolved_strict_subset_prevents_false_minimal_certificate() -> None:
    statuses = {
        (): "NOT_RECOVERED",
        ("a",): "ABSTAINED",
        ("b",): "NOT_RECOVERED",
        ("a", "b"): "RECOVERED",
    }
    family = certified_minimal_family(statuses, ("a", "b"))
    assert family.certified == ()
    assert family.unresolved == (("a", "b"),)


def test_partition_validation_rejects_overlap_and_incomplete_tables() -> None:
    units = ("a", "b")
    statuses = {(): "NOT_RECOVERED"}
    with pytest.raises(ValueError, match="cover"):
        evaluate_partition_topology(units, statuses, (("a",),))
    with pytest.raises(ValueError, match="complete"):
        evaluate_partition_topology(units, statuses, (("a",), ("b",)))
