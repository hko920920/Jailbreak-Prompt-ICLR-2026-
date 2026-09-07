"""Identification and closure audits for finite, possibly nonmonotone oracles.

No inference, payload access, or changes to the frozen topology engine. Bounds
refer to arbitrary Boolean completions of unresolved labels, not ground truth
or confidence intervals. In particular they cannot repair capability confounds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from jbspan.resolution_topology import (
    UnitPartition,
    UnitSubset,
    all_subsets,
    canonical_subset,
    evaluate_partition_topology,
    validate_partition,
)

RECOVERED = "RECOVERED"
NEGATIVE = "NOT_RECOVERED"
UNKNOWN_STATES = frozenset({"ABSTAINED", "CAPABILITY_CONFOUNDED", "UNKNOWN"})


@dataclass(frozen=True)
class FamilyBounds:
    necessary: tuple[UnitSubset, ...]
    possible: tuple[UnitSubset, ...]
    unresolved_rows: tuple[UnitSubset, ...]

    @property
    def identified(self) -> bool:
        return self.necessary == self.possible


def _validate(units: Sequence[str], statuses: Mapping[UnitSubset, str]) -> tuple[UnitSubset, ...]:
    canonical_subset(units, ())
    subsets = all_subsets(units)
    if set(statuses) != set(subsets):
        raise ValueError("a complete table including explicit unresolved rows is required")
    if set(statuses.values()) - {RECOVERED, NEGATIVE} - UNKNOWN_STATES:
        raise ValueError("unrecognized oracle status")
    return subsets


def minimal_family_bounds(units: Sequence[str], statuses: Mapping[UnitSubset, str]) -> FamilyBounds:
    """Sharp marginal membership bounds over all Boolean completions.

    Every completed minimal family contains ``necessary`` and is contained in
    ``possible``. Each possible member occurs in some completion; the possible
    members need not coexist. All strict subsets, not only parents, are checked.
    """

    subsets = _validate(units, statuses)
    necessary: list[UnitSubset] = []
    possible: list[UnitSubset] = []
    for selected in subsets:
        strict = all_subsets(selected)[:-1]
        if statuses[selected] != NEGATIVE and not any(
            statuses[other] == RECOVERED for other in strict
        ):
            possible.append(selected)
        if statuses[selected] == RECOVERED and all(statuses[other] == NEGATIVE for other in strict):
            necessary.append(selected)
    return FamilyBounds(
        tuple(necessary),
        tuple(possible),
        tuple(selected for selected in subsets if statuses[selected] in UNKNOWN_STATES),
    )


def partition_closure(
    units: Sequence[str], partition: UnitPartition, selected: UnitSubset
) -> UnitSubset:
    """Smallest representable union containing selected atomic units."""

    validate_partition(units, partition)
    canonical_subset(units, selected)
    chosen = set(selected)
    return canonical_subset(
        units, (unit for block in partition if chosen.intersection(block) for unit in block)
    )


def closure_null_family(
    units: Sequence[str],
    partition: UnitPartition,
    fine_family: Sequence[UnitSubset],
) -> tuple[UnitSubset, ...]:
    """Minimal closures; equals coarse family for a complete monotone oracle.

    For an incomplete table, plugging in certified minima does NOT make this a
    valid complete null prediction. Callers must expose that distinction.
    """

    validate_partition(units, partition)
    closures = {partition_closure(units, partition, selected) for selected in fine_family}
    minima = {s for s in closures if not any(set(t) < set(s) for t in closures)}
    return tuple(s for s in all_subsets(units) if s in minima)


def audit_partition(
    units: Sequence[str], statuses: Mapping[UnitSubset, str], partition: UnitPartition
) -> dict[str, object]:
    """Separate grouping, hidden uncertainty, and known recovery reversals."""

    fine = minimal_family_bounds(units, statuses)
    coarse = evaluate_partition_topology(units, statuses, partition)
    fine_family = set(fine.necessary)
    coarse_family = set(coarse.certified_atomic_sets)
    witnesses = []
    unresolved_closures = 0
    for selected in fine.necessary:
        closed = partition_closure(units, partition, selected)
        if statuses[closed] == NEGATIVE:
            witnesses.append({"fine_minimum": list(selected), "coarse_union": list(closed)})
        elif statuses[closed] in UNKNOWN_STATES:
            unresolved_closures += 1
    promoted = []
    for selected in coarse.certified_atomic_sets:
        if selected in fine_family:
            continue
        strict = all_subsets(selected)[:-1]
        recovered = [list(other) for other in strict if statuses[other] == RECOVERED]
        unresolved = [list(other) for other in strict if statuses[other] in UNKNOWN_STATES]
        promoted.append(
            {
                "coarse_union": list(selected),
                "hidden_recovered_strict_subsets": recovered,
                "hidden_unresolved_strict_subsets": unresolved,
                "cause": "HIDDEN_RECOVERED_SUBSET" if recovered else "HIDDEN_UNRESOLVED_SUBSET",
            }
        )
    fine_nontrivial = len(fine_family) > 1 or any(len(s) > 1 for s in fine_family)
    complete_binary = not fine.unresolved_rows
    null = closure_null_family(units, partition, fine.necessary) if complete_binary else None
    return {
        "partition": [list(block) for block in partition],
        "coarse_certified_atomic_sets": [list(s) for s in coarse.certified_atomic_sets],
        "family_changed": fine_family != coarse_family,
        "nontrivial_flip": bool(fine_family)
        and coarse.reportable
        and fine_nontrivial != coarse.nontrivial,
        "group_count_only_flip": bool(fine_family)
        and fine_family == coarse_family
        and fine_nontrivial != coarse.nontrivial,
        "certified_adverse_closure_witnesses": witnesses,
        "unresolved_certified_minimum_closures": unresolved_closures,
        "promoted_coarse_certificates": promoted,
        "complete_binary_table": complete_binary,
        "monotone_closure_null_atomic_sets": None if null is None else [list(s) for s in null],
        "closure_null_residual": None if null is None else set(null) != coarse_family,
    }
