"""Content-free retrospective audit; never relabels the frozen D3/C1N result."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from jbspan.resolution_topology import atomic_status_map, set_partitions
from jbspan.topology_identification import audit_partition, minimal_family_bounds

SOURCE = "data/natural_language_localization/d3_exact_topology_v1/instance_results.safe.jsonl"
SOURCE_SHA256 = "2ebe3ff8cf7a603fa885500e9946bb79cdc7bd80d79f6ea29077dfb099934d34"
OUTPUT = "data/natural_language_localization/rescue_identification_v2/audit.safe.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(rows: list[dict]) -> dict:
    def partitions(kind):
        return [p for row in rows for p in row[kind]]

    def spectrum(kind):
        items = partitions(kind)
        return {
            "comparison_count": len(items),
            "setwise_family_change_count": sum(p["family_changed"] for p in items),
            "ordering_only_false_change_count": sum(p["ordering_only_false_change"] for p in items),
            "group_count_only_flip_count": sum(p["group_count_only_flip"] for p in items),
            "nontrivial_flip_count": sum(p["nontrivial_flip"] for p in items),
            "certified_adverse_closure_comparison_count": sum(
                bool(p["certified_adverse_closure_witnesses"]) for p in items
            ),
            "certified_adverse_closure_witness_count": sum(
                len(p["certified_adverse_closure_witnesses"]) for p in items
            ),
            "complete_binary_comparison_count": sum(p["complete_binary_table"] for p in items),
            "closure_null_residual_count_on_complete_binary": sum(
                p["closure_null_residual"] is True for p in items
            ),
            "unresolved_closure_count": sum(
                p["unresolved_certified_minimum_closures"] for p in items
            ),
            "instances_with_certified_adverse_closure": sum(
                any(p["certified_adverse_closure_witnesses"] for p in row[kind]) for row in rows
            ),
            "unique_payloads_with_certified_adverse_closure": len(
                {
                    row["payload_sha256"]
                    for row in rows
                    if any(p["certified_adverse_closure_witnesses"] for p in row[kind])
                }
            ),
        }

    return {
        "instance_count": len(rows),
        "unique_payload_count": len({row["payload_sha256"] for row in rows}),
        "fully_observed_boolean_table_count": sum(not row["unresolved_row_count"] for row in rows),
        "identified_minimal_family_count": sum(row["family_identified"] for row in rows),
        "necessary_minimum_count": sum(len(row["necessary_minima"]) for row in rows),
        "possible_minimum_count": sum(len(row["possible_minima"]) for row in rows),
        "adjacent_one_merge": spectrum("adjacent_one_merge"),
        "arbitrary_one_merge": spectrum("arbitrary_one_merge"),
    }


def run(root: Path) -> dict:
    source = root / SOURCE
    if digest(source) != SOURCE_SHA256:
        raise ValueError("frozen safe D3 source identity mismatch")
    inputs = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    if len(inputs) != 12:
        raise ValueError("unexpected source denominator")
    rows = []
    for item in inputs:
        units = tuple(item["unit_ids"])
        statuses = atomic_status_map(item)
        bounds = minimal_family_bounds(units, statuses)
        stored = tuple(tuple(s) for s in item["minimal_sets"])
        if set(stored) != set(bounds.necessary):
            raise ValueError("necessary family fails to reconstruct frozen D3 minima")
        arbitrary, adjacent = [], []
        for partition in set_partitions(units):
            if len(partition) != len(units) - 1:
                continue
            audit = audit_partition(units, statuses, partition)
            old_ordered = tuple(tuple(s) for s in audit["coarse_certified_atomic_sets"])
            audit["ordering_only_false_change"] = (
                old_ordered != stored and not audit["family_changed"]
            )
            arbitrary.append(audit)
            merged = next(block for block in partition if len(block) == 2)
            if units.index(merged[1]) == units.index(merged[0]) + 1:
                adjacent.append(audit)
        rows.append(
            {
                "instance_id": item["instance_id"],
                "attack_family": item["attack_family"],
                "payload_sha256": item["payload_sha256"],
                "unit_ids": list(units),
                "status_counts": dict(Counter(statuses.values())),
                "unresolved_row_count": len(bounds.unresolved_rows),
                "family_identified": bounds.identified,
                "necessary_minima": [list(s) for s in bounds.necessary],
                "possible_minima": [list(s) for s in bounds.possible],
                "adjacent_one_merge": adjacent,
                "arbitrary_one_merge": arbitrary,
            }
        )
    families = sorted({row["attack_family"] for row in rows})
    result = {
        "schema_version": "jbspan-rescue-identification-audit-v2",
        "evidence_class": "RETROSPECTIVE_EXPLORATORY_METHOD_AUDIT_NOT_CONFIRMATION",
        "status": "AUDIT_COMPLETE_NO_SCIENTIFIC_SUCCESS_GATE",
        "source_sha256": SOURCE_SHA256,
        "analysis_sha256": {
            name: digest(root / name)
            for name in (
                "src/jbspan/topology_identification.py",
                "scripts/audit_rescue_identification_v2.py",
            )
        },
        "scope": {
            "new_target_calls": 0,
            "new_judge_calls": 0,
            "raw_content_read": False,
            "primary_a_opened": False,
            "reserve_b_opened": False,
            "d3_or_c1n_reclassified": False,
        },
        "interpretation": {
            "bounds": (
                "Sharp membership bounds over hypothetical completions, not CI or human truth."
            ),
            "confounds": "Capability-confounded rows remain unresolved, never repaired evidence.",
            "witness": "Known recovery at a fine minimum; known non-recovery at its closure.",
            "null": "Complete Boolean tables only; unresolved rows are never imputed.",
            "sampling_unit": "Unique payload; partitions are repeated deterministic views.",
        },
        "overall": summarize(rows),
        "by_family": {
            family: summarize([r for r in rows if r["attack_family"] == family])
            for family in families
        },
        "per_instance": rows,
    }
    result["result_identity_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    result = run(root)
    destination = root / OUTPUT
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise ValueError("write-once audit already exists with different content")
    else:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    print(
        json.dumps(
            {
                "overall": result["overall"],
                "by_family": result["by_family"],
                "result_identity_sha256": result["result_identity_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
