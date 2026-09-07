"""Outcome-preserving D3 resolution-sensitivity rescue audit.

This script reads only safe, content-free exact-topology records.  It performs
no target or evaluator inference and cannot retroactively alter the official D3
or C1N decisions.  Its sole purpose is to decide whether a separately frozen,
fresh study of explanation specification-sensitivity is worth attempting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jbspan.resolution_topology import (
    PartitionTopology,
    UnitPartition,
    atomic_status_map,
    contiguous_partitions,
    evaluate_partition_topology,
    set_partitions,
)

JsonObject = dict[str, Any]
JsonRows = list[JsonObject]
PROHIBITED_KEYS = {
    "payload",
    "prompt",
    "response",
    "response_text",
    "goal_text",
    "assistant_response",
    "human_request",
    "content",
    "raw_output",
    "stdout",
    "stderr",
    "input_token_ids",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/"
            "d3_resolution_rescue_audit_v1.json"
        ),
    )
    value.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/natural_language_localization/d3_exact_topology_v1/"
            "postoutcome_resolution_rescue_audit.safe.json"
        ),
    )
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> JsonRows:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON object rows: {path}")
    return rows


def resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def verify_dependencies(root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, dependency in config["dependencies"].items():
        path = resolve(root, str(dependency["path"]))
        digest = file_sha256(path)
        if digest != dependency["sha256"]:
            raise ValueError(f"dependency hash mismatch: {name}")
        observed[str(name)] = digest
    return observed


def _partition_groups(partition: UnitPartition) -> list[list[str]]:
    return [list(block) for block in partition]


def _minimal_sets(topology: PartitionTopology) -> list[list[str]]:
    return [list(subset) for subset in topology.certified_atomic_sets]


def _partition_row(
    topology: PartitionTopology,
    reference_sets: tuple[tuple[str, ...], ...],
    reference_reportable: bool,
    reference_nontrivial: bool,
) -> JsonObject:
    family = tuple(topology.certified_atomic_sets)
    return {
        "groups": _partition_groups(topology.partition),
        "block_count": len(topology.partition),
        "reportable": topology.reportable,
        "minimum_recovery_order": topology.minimum_order,
        "minimal_set_count": len(topology.certified_atomic_sets),
        "minimal_sets_as_atomic_units": _minimal_sets(topology),
        "unresolved_minimal_candidate_count": len(topology.unresolved_atomic_sets),
        "multiple_pathways": topology.multiple_pathways,
        "has_nonsingleton": topology.has_nonsingleton,
        "nontrivial": topology.nontrivial,
        "exact_reference_family_match": reference_reportable
        and topology.reportable
        and family == reference_sets,
        "reportability_changed": topology.reportable != reference_reportable,
        "nontrivial_classification_changed": (
            reference_reportable
            and topology.reportable
            and topology.nontrivial != reference_nontrivial
        ),
        "family_changed": family != reference_sets,
    }


def _summarize_partition_rows(rows: Sequence[Mapping[str, Any]]) -> JsonObject:
    by_blocks: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_blocks[int(row["block_count"])].append(row)
    return {
        "partition_count": len(rows),
        "by_block_count": {
            str(block_count): {
                "partition_count": len(group),
                "reportable_count": sum(bool(row["reportable"]) for row in group),
                "nontrivial_count": sum(bool(row["nontrivial"]) for row in group),
                "multiple_pathway_count": sum(
                    bool(row["multiple_pathways"]) for row in group
                ),
                "nonsingleton_count": sum(
                    bool(row["has_nonsingleton"]) for row in group
                ),
                "family_changed_count": sum(
                    bool(row["family_changed"]) for row in group
                ),
                "reportability_changed_count": sum(
                    bool(row["reportability_changed"]) for row in group
                ),
                "nontrivial_classification_changed_count": sum(
                    bool(row["nontrivial_classification_changed"]) for row in group
                ),
                "minimum_recovery_order_counts": dict(
                    sorted(
                        Counter(
                            str(row["minimum_recovery_order"])
                            for row in group
                            if row["minimum_recovery_order"] is not None
                        ).items()
                    )
                ),
            }
            for block_count, group in sorted(by_blocks.items(), reverse=True)
        },
    }


def _instance_summary(instance: Mapping[str, Any]) -> JsonObject:
    units = tuple(str(unit) for unit in instance["unit_ids"])
    statuses = atomic_status_map(instance)
    fine_partition = tuple((unit,) for unit in units)
    fine = evaluate_partition_topology(units, statuses, fine_partition)
    stored_sets = tuple(
        tuple(str(unit) for unit in subset) for subset in instance["minimal_sets"]
    )
    if fine.certified_atomic_sets != stored_sets:
        raise ValueError("atomic partition does not reconstruct stored minimal family")
    if len(fine.certified_atomic_sets) != int(instance["minimal_set_count"]):
        raise ValueError("atomic partition minimal count differs from D3")

    reference_reportable = fine.reportable
    reference_nontrivial = fine.nontrivial
    contiguous = [
        _partition_row(
            evaluate_partition_topology(units, statuses, partition),
            stored_sets,
            reference_reportable,
            reference_nontrivial,
        )
        for partition in contiguous_partitions(units)
    ]
    all_partitions = [
        _partition_row(
            evaluate_partition_topology(units, statuses, partition),
            stored_sets,
            reference_reportable,
            reference_nontrivial,
        )
        for partition in set_partitions(units)
    ]
    contiguous_one_merge = [
        row for row in contiguous if int(row["block_count"]) == len(units) - 1
    ]
    arbitrary_one_merge = [
        row for row in all_partitions if int(row["block_count"]) == len(units) - 1
    ]
    immediate_instability = [
        row
        for row in arbitrary_one_merge
        if row["reportability_changed"] or row["family_changed"]
    ]
    immediate_trivializations = [
        row
        for row in arbitrary_one_merge
        if reference_nontrivial and row["reportable"] and not row["nontrivial"]
    ]
    return {
        "instance_id": instance["instance_id"],
        "attack_family": instance["attack_family"],
        "payload_sha256": instance["payload_sha256"],
        "topic_sha256": instance["topic_sha256"],
        "source_payload_position": instance["source_payload_position"],
        "unit_ids": list(units),
        "unit_count": len(units),
        "atomic_truth_table_count": len(statuses),
        "reference": {
            "reportable": reference_reportable,
            "minimal_sets": [list(subset) for subset in stored_sets],
            "minimal_set_count": len(stored_sets),
            "minimum_recovery_order": fine.minimum_order,
            "nontrivial": reference_nontrivial,
            "multiple_pathways": fine.multiple_pathways,
            "has_nonsingleton": fine.has_nonsingleton,
        },
        "contiguous_partition_spectrum": _summarize_partition_rows(contiguous),
        "all_partition_spectrum": _summarize_partition_rows(all_partitions),
        "contiguous_one_merge": contiguous_one_merge,
        "arbitrary_one_merge": arbitrary_one_merge,
        "immediate_arbitrary_one_merge_instability_count": len(immediate_instability),
        "immediate_arbitrary_one_merge_trivialization_count": len(
            immediate_trivializations
        ),
    }


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> JsonObject:
    fine_nontrivial = [row for row in rows if row["reference"]["nontrivial"]]
    payloads_with_instability = {
        str(row["payload_sha256"])
        for row in rows
        if int(row["immediate_arbitrary_one_merge_instability_count"]) > 0
    }
    payloads_with_trivialization = {
        str(row["payload_sha256"])
        for row in rows
        if int(row["immediate_arbitrary_one_merge_trivialization_count"]) > 0
    }
    one_merge_rows = [
        partition
        for row in rows
        for partition in row["arbitrary_one_merge"]
    ]
    contiguous_one_merge_rows = [
        partition
        for row in rows
        for partition in row["contiguous_one_merge"]
    ]
    return {
        "instance_count": len(rows),
        "unique_payload_count": len({str(row["payload_sha256"]) for row in rows}),
        "reference_reportable_count": sum(
            bool(row["reference"]["reportable"]) for row in rows
        ),
        "reference_nontrivial_count": len(fine_nontrivial),
        "reference_multiple_pathway_count": sum(
            bool(row["reference"]["multiple_pathways"]) for row in rows
        ),
        "all_partition_count": sum(
            int(row["all_partition_spectrum"]["partition_count"]) for row in rows
        ),
        "contiguous_partition_count": sum(
            int(row["contiguous_partition_spectrum"]["partition_count"])
            for row in rows
        ),
        "arbitrary_one_merge_comparison_count": len(one_merge_rows),
        "arbitrary_one_merge_family_changed_count": sum(
            bool(row["family_changed"]) for row in one_merge_rows
        ),
        "arbitrary_one_merge_reportability_changed_count": sum(
            bool(row["reportability_changed"]) for row in one_merge_rows
        ),
        "arbitrary_one_merge_nontrivial_flip_count": sum(
            bool(row["nontrivial_classification_changed"]) for row in one_merge_rows
        ),
        "contiguous_one_merge_comparison_count": len(contiguous_one_merge_rows),
        "contiguous_one_merge_family_changed_count": sum(
            bool(row["family_changed"]) for row in contiguous_one_merge_rows
        ),
        "contiguous_one_merge_reportability_changed_count": sum(
            bool(row["reportability_changed"]) for row in contiguous_one_merge_rows
        ),
        "contiguous_one_merge_nontrivial_flip_count": sum(
            bool(row["nontrivial_classification_changed"])
            for row in contiguous_one_merge_rows
        ),
        "instances_with_any_immediate_instability": sum(
            int(row["immediate_arbitrary_one_merge_instability_count"]) > 0
            for row in rows
        ),
        "instances_with_immediate_trivialization": sum(
            int(row["immediate_arbitrary_one_merge_trivialization_count"]) > 0
            for row in rows
        ),
        "unique_payloads_with_any_immediate_instability": len(payloads_with_instability),
        "unique_payloads_with_immediate_trivialization": len(
            payloads_with_trivialization
        ),
    }


def _assert_no_prohibited_keys(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in PROHIBITED_KEYS:
                joined = ".".join((*path, str(key)))
                raise ValueError(f"prohibited raw field in safe result: {joined}")
            _assert_no_prohibited_keys(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_prohibited_keys(child, (*path, str(index)))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_file = resolve(root, config_path)
    config = load_object(config_file)
    if config.get("status") != "FROZEN_BEFORE_RESOLUTION_SPECTRUM_OUTPUT":
        raise ValueError("resolution rescue audit config is not frozen")
    if config.get("official_d3_or_c1n_relabeling_allowed") is not False:
        raise ValueError("audit must prohibit D3 and C1N relabeling")
    observed_dependencies = verify_dependencies(root, config)
    instance_path = resolve(root, config["inputs"]["instance_results_path"])
    instances = load_jsonl(instance_path)
    expected_instances = int(config["inputs"]["expected_instance_count"])
    if len(instances) != expected_instances:
        raise ValueError("unexpected D3 instance denominator")
    summaries = [_instance_summary(instance) for instance in instances]
    by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in summaries:
        by_family[str(row["attack_family"])].append(row)
    family_aggregates = {
        family: _aggregate(rows) for family, rows in sorted(by_family.items())
    }
    overall = _aggregate(summaries)

    thresholds = config["feasibility_gate"]
    family_signal = {
        family: (
            aggregate["reference_nontrivial_count"]
            >= int(thresholds["minimum_reference_nontrivial_per_family"])
            and aggregate["instances_with_any_immediate_instability"]
            >= int(thresholds["minimum_immediately_unstable_per_family"])
        )
        for family, aggregate in family_aggregates.items()
    }
    checks = {
        "two_attack_families_present": len(family_aggregates) >= 2,
        "each_family_has_nontrivial_and_immediate_instability_signal": all(
            family_signal.values()
        ),
        "unique_payload_instability_minimum": overall[
            "unique_payloads_with_any_immediate_instability"
        ]
        >= int(thresholds["minimum_unique_payloads_with_immediate_instability"]),
        "reference_nontrivial_minimum": overall["reference_nontrivial_count"]
        >= int(thresholds["minimum_reference_nontrivial_overall"]),
    }
    passes = all(checks.values())
    result: JsonObject = {
        "schema_version": "jbspan-d3-resolution-rescue-audit-v1",
        "status": (
            "POSTOUTCOME_RESOLUTION_RESCUE_FEASIBILITY_SIGNAL_PASS"
            if passes
            else "POSTOUTCOME_RESOLUTION_RESCUE_FEASIBILITY_SIGNAL_FAIL"
        ),
        "evidence_class": (
            "POSTOUTCOME_EXPLORATORY_DIAGNOSTIC_NOT_CONFIRMATORY_EVIDENCE"
        ),
        "config_sha256": file_sha256(config_file),
        "verified_dependency_sha256": observed_dependencies,
        "source_instance_results_file_sha256": file_sha256(instance_path),
        "projection_claim": (
            "Every intervention representable by a partition is an atomic-unit union "
            "already present in the complete D3 truth table; no new target or evaluator "
            "call is required for this diagnostic."
        ),
        "scope": {
            "official_d3_reclassified": False,
            "official_c1n_reclassified": False,
            "new_target_inference": False,
            "new_evaluator_inference": False,
            "new_human_annotation": False,
            "raw_text_read": False,
            "raw_text_written": False,
            "paper_valid_confirmatory_claim": False,
        },
        "overall": overall,
        "by_family": family_aggregates,
        "per_instance": summaries,
        "feasibility_gate": {
            "checks": checks,
            "family_signal": family_signal,
            "passes_all": passes,
            "meaning": (
                "Passing authorizes only a separately frozen fresh-holdout design. "
                "It does not validate a paper claim or reopen C2N."
            ),
        },
        "next_operation": (
            "FREEZE_FRESH_SPECIFICATION_SENSITIVITY_STUDY_ON_UNTOUCHED_ROWS"
            if passes
            else "STOP_RESOLUTION_SENSITIVITY_PIVOT"
        ),
    }
    _assert_no_prohibited_keys(result)
    result["result_identity_sha256"] = canonical_sha256(result)
    return result


def main() -> None:
    arguments = parser().parse_args()
    root = arguments.root.resolve()
    result = run(root, arguments.config)
    output = resolve(root, arguments.output)
    _write_json(output, result)
    print(json.dumps(result["feasibility_gate"], ensure_ascii=False, indent=2))
    print(f"result_identity_sha256={result['result_identity_sha256']}")


if __name__ == "__main__":
    main()
