"""Independent exhaustive truth-table checks, plus nonmonotone counterexamples."""

import itertools

import pytest

from jbspan.resolution_topology import all_subsets, set_partitions
from jbspan.topology_identification import (
    audit_partition,
    closure_null_family,
    minimal_family_bounds,
)


def brute_minima(subsets, bits):
    positives = {s for s, bit in zip(subsets, bits, strict=True) if bit}
    return {s for s in positives if not any(set(t) < set(s) for t in positives)}


def test_bounds_against_every_completion_of_every_three_unit_partial_table():
    units = ("a", "b", "c")
    subsets = all_subsets(units)
    for values in itertools.product((0, 1, 2), repeat=len(subsets)):
        statuses = dict(
            zip(
                subsets,
                ({0: "NOT_RECOVERED", 1: "RECOVERED", 2: "UNKNOWN"}[v] for v in values),
                strict=True,
            )
        )
        bounds = minimal_family_bounds(units, statuses)
        unknown = [i for i, v in enumerate(values) if v == 2]
        intersection, union = set(subsets), set()
        for replacement in itertools.product((0, 1), repeat=len(unknown)):
            bits = list(values)
            for index, bit in zip(unknown, replacement, strict=True):
                bits[index] = bit
            family = brute_minima(subsets, bits)
            intersection.intersection_update(family)
            union.update(family)
        assert set(bounds.necessary) == intersection
        assert set(bounds.possible) == union


def test_unknown_itself_can_be_a_possible_minimum():
    result = minimal_family_bounds(("a",), {(): "NOT_RECOVERED", ("a",): "UNKNOWN"})
    assert result.necessary == ()
    assert result.possible == (("a",),)


def test_group_count_flip_can_have_identical_atomic_family():
    statuses = {
        (): "NOT_RECOVERED",
        ("a",): "NOT_RECOVERED",
        ("b",): "NOT_RECOVERED",
        ("a", "b"): "RECOVERED",
    }
    result = audit_partition(("a", "b"), statuses, (("a", "b"),))
    assert result["group_count_only_flip"]
    assert not result["family_changed"]
    assert not result["closure_null_residual"]


def test_nonmonotone_closure_can_break_recovery_despite_containing_minimum():
    statuses = {
        (): "NOT_RECOVERED",
        ("a",): "RECOVERED",
        ("b",): "NOT_RECOVERED",
        ("a", "b"): "NOT_RECOVERED",
    }
    result = audit_partition(("a", "b"), statuses, (("a", "b"),))
    assert len(result["certified_adverse_closure_witnesses"]) == 1
    assert result["closure_null_residual"]


def test_coarsening_can_hide_unknown_strict_subset():
    statuses = {
        (): "NOT_RECOVERED",
        ("a",): "ABSTAINED",
        ("b",): "NOT_RECOVERED",
        ("a", "b"): "RECOVERED",
    }
    result = audit_partition(("a", "b"), statuses, (("a", "b"),))
    assert result["promoted_coarse_certificates"][0]["cause"] == "HIDDEN_UNRESOLVED_SUBSET"
    assert result["closure_null_residual"] is None


def test_monotone_closure_identity_for_all_three_unit_boolean_tables_and_partitions():
    units = ("a", "b", "c")
    subsets = all_subsets(units)
    monotone_count = 0
    for bits in itertools.product((0, 1), repeat=len(subsets)):
        table = dict(zip(subsets, bits, strict=True))
        if any(table[s] > table[t] for s in subsets for t in subsets if set(s) < set(t)):
            continue
        monotone_count += 1
        fine = brute_minima(subsets, bits)
        for partition in set_partitions(units):
            representable = [
                s
                for s in subsets
                if all(
                    not set(block).intersection(s) or set(block).issubset(s) for block in partition
                )
            ]
            exact = brute_minima(representable, [table[s] for s in representable])
            assert set(closure_null_family(units, partition, tuple(fine))) == exact
    assert monotone_count == 20


def test_reordered_identical_atomic_family_is_not_a_change():
    units = ("a", "b", "c")
    statuses = {
        s: "RECOVERED" if "c" in s or {"a", "b"}.issubset(s) else "NOT_RECOVERED"
        for s in all_subsets(units)
    }
    result = audit_partition(units, statuses, (("a", "b"), ("c",)))
    assert not result["family_changed"]
    assert not result["closure_null_residual"]


def test_bad_status_and_incomplete_table_fail_closed():
    with pytest.raises(ValueError, match="complete table"):
        minimal_family_bounds(("a",), {(): "NOT_RECOVERED"})
    with pytest.raises(ValueError, match="unrecognized"):
        minimal_family_bounds(("a",), {(): "NOT_RECOVERED", ("a",): "TYPO"})
