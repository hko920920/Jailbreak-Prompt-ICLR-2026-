"""Exact recovery-topology projection across intervention-unit partitions.

The functions in this module never call a target model or evaluator.  A complete
atomic truth table already contains the outcome of every union of atomic units,
so it also contains every intervention representable by any coarsening of those
units.  We use that fact to measure how strongly a minimal-recovery explanation
depends on the chosen intervention vocabulary.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

UnitSubset = tuple[str, ...]
UnitBlock = tuple[str, ...]
UnitPartition = tuple[UnitBlock, ...]


def _validate_units(unit_ids: Sequence[str]) -> UnitSubset:
    units = tuple(unit_ids)
    if not units:
        raise ValueError("unit_ids must be non-empty")
    if any(not unit.strip() for unit in units):
        raise ValueError("unit_ids must be non-empty strings")
    if len(units) != len(set(units)):
        raise ValueError("unit_ids must be unique")
    return units


def canonical_subset(unit_ids: Sequence[str], selected: Iterable[str]) -> UnitSubset:
    """Return ``selected`` in the declared atomic-unit order."""

    units = _validate_units(unit_ids)
    supplied = tuple(selected)
    if len(supplied) != len(set(supplied)):
        raise ValueError("selected units must be unique")
    unknown = set(supplied) - set(units)
    if unknown:
        raise ValueError(f"unknown selected units: {sorted(unknown)}")
    selected_set = set(supplied)
    return tuple(unit for unit in units if unit in selected_set)


def all_subsets(values: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    ordered = tuple(values)
    if len(ordered) != len(set(ordered)):
        raise ValueError("subset universe must be unique")
    return tuple(
        tuple(subset)
        for size in range(len(ordered) + 1)
        for subset in itertools.combinations(ordered, size)
    )


def contiguous_partitions(unit_ids: Sequence[str]) -> tuple[UnitPartition, ...]:
    """Enumerate every order-preserving contiguous partition deterministically."""

    units = _validate_units(unit_ids)
    output: list[UnitPartition] = []
    for cut_mask in range(1 << (len(units) - 1)):
        blocks: list[UnitBlock] = []
        start = 0
        for boundary in range(len(units) - 1):
            if cut_mask & (1 << boundary):
                blocks.append(units[start : boundary + 1])
                start = boundary + 1
        blocks.append(units[start:])
        output.append(tuple(blocks))
    return tuple(
        sorted(
            output,
            key=lambda partition: (
                -len(partition),
                tuple(tuple(units.index(unit) for unit in block) for block in partition),
            ),
        )
    )


def set_partitions(unit_ids: Sequence[str]) -> tuple[UnitPartition, ...]:
    """Enumerate every set partition in canonical first-element block order."""

    units = _validate_units(unit_ids)

    def build(index: int, blocks: tuple[UnitBlock, ...]) -> Iterable[UnitPartition]:
        if index == len(units):
            yield blocks
            return
        unit = units[index]
        for block_index in range(len(blocks)):
            amended = list(blocks)
            amended[block_index] = (*amended[block_index], unit)
            yield from build(index + 1, tuple(amended))
        yield from build(index + 1, (*blocks, (unit,)))

    partitions = tuple(build(1, ((units[0],),)))
    return tuple(
        sorted(
            partitions,
            key=lambda partition: (
                -len(partition),
                tuple(tuple(units.index(unit) for unit in block) for block in partition),
            ),
        )
    )


def validate_partition(unit_ids: Sequence[str], partition: UnitPartition) -> None:
    units = _validate_units(unit_ids)
    if not partition or any(not block for block in partition):
        raise ValueError("partition blocks must be non-empty")
    flattened = tuple(unit for block in partition for unit in block)
    if len(flattened) != len(set(flattened)):
        raise ValueError("partition blocks overlap")
    if set(flattened) != set(units):
        raise ValueError("partition must cover the atomic universe exactly")
    positions = {unit: index for index, unit in enumerate(units)}
    if any(
        tuple(sorted(block, key=positions.__getitem__)) != block for block in partition
    ):
        raise ValueError("units within each partition block must retain atomic order")
    block_first_positions = tuple(positions[block[0]] for block in partition)
    if tuple(sorted(block_first_positions)) != block_first_positions:
        raise ValueError("partition blocks must be ordered by their first atomic unit")


def _validate_atomic_statuses(
    unit_ids: UnitSubset, atomic_statuses: Mapping[UnitSubset, str]
) -> None:
    expected = set(all_subsets(unit_ids))
    observed = set(atomic_statuses)
    if observed != expected:
        missing = len(expected - observed)
        extra = len(observed - expected)
        raise ValueError(
            f"atomic truth table must be complete (missing={missing}, extra={extra})"
        )


def project_statuses(
    unit_ids: Sequence[str],
    atomic_statuses: Mapping[UnitSubset, str],
    partition: UnitPartition,
) -> tuple[tuple[str, ...], dict[tuple[str, ...], str], dict[tuple[str, ...], UnitSubset]]:
    """Project a complete atomic table onto one coarsened vocabulary."""

    units = _validate_units(unit_ids)
    validate_partition(units, partition)
    _validate_atomic_statuses(units, atomic_statuses)
    block_ids = tuple(f"G{index}" for index in range(len(partition)))
    status_by_groups: dict[tuple[str, ...], str] = {}
    atomic_by_groups: dict[tuple[str, ...], UnitSubset] = {}
    for selected_groups in all_subsets(block_ids):
        selected_indexes = {int(group_id[1:]) for group_id in selected_groups}
        selected_units = canonical_subset(
            units,
            (
                unit
                for block_index, block in enumerate(partition)
                if block_index in selected_indexes
                for unit in block
            ),
        )
        status_by_groups[selected_groups] = atomic_statuses[selected_units]
        atomic_by_groups[selected_groups] = selected_units
    return block_ids, status_by_groups, atomic_by_groups


@dataclass(frozen=True)
class MinimalFamily:
    certified: tuple[tuple[str, ...], ...]
    unresolved: tuple[tuple[str, ...], ...]


def certified_minimal_family(
    statuses: Mapping[tuple[str, ...], str],
    universe_order: Sequence[str],
    *,
    recovered_status: str = "RECOVERED",
    negative_status: str = "NOT_RECOVERED",
) -> MinimalFamily:
    """Find every strict-subset-minimal recovered set without assuming monotonicity."""

    universe = tuple(universe_order)
    expected = set(all_subsets(universe))
    if set(statuses) != expected:
        raise ValueError("coarsened truth table must be complete")
    recovered = [subset for subset in all_subsets(universe) if statuses[subset] == recovered_status]
    candidates = [
        subset
        for subset in recovered
        if not any(set(other) < set(subset) for other in recovered)
    ]
    certified: list[tuple[str, ...]] = []
    unresolved: list[tuple[str, ...]] = []
    for candidate in candidates:
        strict = [subset for subset in all_subsets(candidate) if subset != candidate]
        if all(statuses[subset] == negative_status for subset in strict):
            certified.append(candidate)
        else:
            unresolved.append(candidate)
    return MinimalFamily(tuple(certified), tuple(unresolved))


@dataclass(frozen=True)
class PartitionTopology:
    partition: UnitPartition
    block_ids: tuple[str, ...]
    certified_group_sets: tuple[tuple[str, ...], ...]
    certified_atomic_sets: tuple[UnitSubset, ...]
    unresolved_group_sets: tuple[tuple[str, ...], ...]
    unresolved_atomic_sets: tuple[UnitSubset, ...]

    @property
    def reportable(self) -> bool:
        return bool(self.certified_group_sets)

    @property
    def minimum_order(self) -> int | None:
        if not self.certified_group_sets:
            return None
        return min(len(subset) for subset in self.certified_group_sets)

    @property
    def multiple_pathways(self) -> bool:
        return len(self.certified_group_sets) > 1

    @property
    def has_nonsingleton(self) -> bool:
        return any(len(subset) > 1 for subset in self.certified_group_sets)

    @property
    def nontrivial(self) -> bool:
        return self.multiple_pathways or self.has_nonsingleton


def evaluate_partition_topology(
    unit_ids: Sequence[str],
    atomic_statuses: Mapping[UnitSubset, str],
    partition: UnitPartition,
) -> PartitionTopology:
    block_ids, statuses, atomic_by_groups = project_statuses(
        unit_ids, atomic_statuses, partition
    )
    family = certified_minimal_family(statuses, block_ids)
    return PartitionTopology(
        partition=partition,
        block_ids=block_ids,
        certified_group_sets=family.certified,
        certified_atomic_sets=tuple(atomic_by_groups[subset] for subset in family.certified),
        unresolved_group_sets=family.unresolved,
        unresolved_atomic_sets=tuple(atomic_by_groups[subset] for subset in family.unresolved),
    )


def atomic_status_map(instance: Mapping[str, object]) -> dict[UnitSubset, str]:
    """Read the content-free subset-decision projection from one safe D3 row."""

    raw_units = instance.get("unit_ids")
    raw_decisions = instance.get("subset_decisions")
    if not isinstance(raw_units, list) or not all(isinstance(unit, str) for unit in raw_units):
        raise ValueError("instance unit_ids are malformed")
    units = _validate_units(raw_units)
    if not isinstance(raw_decisions, list):
        raise ValueError("instance subset_decisions are malformed")
    output: dict[UnitSubset, str] = {}
    for raw in raw_decisions:
        if not isinstance(raw, dict):
            raise ValueError("subset decision must be an object")
        selected = raw.get("selected_unit_ids")
        status = raw.get("status")
        if not isinstance(selected, list) or not all(isinstance(unit, str) for unit in selected):
            raise ValueError("subset decision selected_unit_ids are malformed")
        if not isinstance(status, str):
            raise ValueError("subset decision status is malformed")
        subset = canonical_subset(units, selected)
        if subset in output:
            raise ValueError("duplicate subset decision")
        output[subset] = status
    _validate_atomic_statuses(units, output)
    return output
