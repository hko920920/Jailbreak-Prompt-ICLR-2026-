"""Hash-pinned, content-free retrospective P/A structural reentry audit.

Only the already public-safe D3 decision artifact is read. No inference, judge,
private receipt, sealed sample, or previous audit execution is involved.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = "data/natural_language_localization/d3_exact_topology_v1/instance_results.safe.jsonl"
SOURCE_SHA256 = "2ebe3ff8cf7a603fa885500e9946bb79cdc7bd80d79f6ea29077dfb099934d34"
OUTPUT = "data/natural_language_localization/pa_structural_reentry_v1/audit.safe.json"
SCRIPT = "scripts/audit_pa_structural_reentry_v1.py"
UNITS = (
    "AIMDecorator",
    "RefusalSuppressionDecorator",
    "AffirmativePrefixInjectionDecorator",
)
STATUS_VALUE = {
    "RECOVERED": 1,
    "NOT_RECOVERED": 0,
    "ABSTAINED": None,
    "CAPABILITY_CONFOUNDED": None,
    "UNKNOWN": None,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_minima(values: tuple[int, ...]) -> tuple[int, ...]:
    """All strict-subset minimal positives, with no monotonicity assumption."""
    return tuple(
        mask
        for mask, value in enumerate(values)
        if value == 1
        and not any(
            values[other] == 1 and other != mask and other & mask == other
            for other in range(len(values))
        )
    )


def completions(values: tuple[int | None, ...]) -> tuple[tuple[int, ...], ...]:
    if not values or len(values) & (len(values) - 1) or len(values) > 8:
        raise ValueError("audit accepts a full truth vector of at most three units")
    if any(value not in (0, 1, None) for value in values):
        raise ValueError("values must be 0, 1, or explicit UNKNOWN")
    unknown = [index for index, value in enumerate(values) if value is None]
    output = []
    for assigned in itertools.product((0, 1), repeat=len(unknown)):
        completed = list(values)
        for index, value in zip(unknown, assigned, strict=True):
            completed[index] = value
        output.append(tuple(completed))
    return tuple(output)


def characterize(values: tuple[int | None, ...], macro: int = 3) -> dict:
    tables = completions(values)
    if macro <= 0 or macro >= len(values):
        raise ValueError("macro must be a nonempty mask in the table")
    families = tuple(sorted({strict_minima(table) for table in tables}))
    necessary = set(families[0]).intersection(*map(set, families[1:]))
    possible = set().union(*map(set, families))
    cardinalities = [
        min((mask.bit_count() for mask in family), default=None) for family in families
    ]
    if any(value is None for value in cardinalities):
        order_bounds = None
    else:
        order_bounds = [min(cardinalities), max(cardinalities)]
    macro_minimal = (
        "CERTIFIED_MINIMAL"
        if macro in necessary
        else "CERTIFIED_NOT_MINIMAL"
        if macro not in possible
        else "UNRESOLVED"
    )
    known_contradictions = [
        mask
        for mask, value in enumerate(values)
        if value is not None and value != int(mask & macro == macro)
    ]
    coarse_masks = (0, macro, (len(values) - 1) ^ macro, len(values) - 1)
    return {
        "truth_vector_mask_order": list(values),
        "complete_binary": None not in values,
        "unknown_mask_ids": [i for i, value in enumerate(values) if value is None],
        "compatible_strict_minimal_families": [list(family) for family in families],
        "necessary_strict_minimum_masks": sorted(necessary),
        "possible_strict_minimum_masks": sorted(possible),
        "family_identified": len(families) == 1,
        "minimum_recovery_cardinality_completion_bounds": order_bounds,
        "fixed_macro_status": values[macro],
        "fixed_macro_strict_minimality": macro_minimal,
        "fixed_macro_only_explanation_known_contradiction_masks": known_contradictions,
        "coarse_representable_mask_ids": list(coarse_masks),
        "coarse_truth_vector": [values[mask] for mask in coarse_masks],
    }


def compare(left: dict, right: dict) -> dict:
    a, b = left["truth_vector_mask_order"], right["truth_vector_mask_order"]
    contradictions = [
        i
        for i, (x, y) in enumerate(zip(a, b, strict=True))
        if x is not None and y is not None and x != y
    ]
    unresolved = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x is None or y is None]
    left_families = {tuple(family) for family in left["compatible_strict_minimal_families"]}
    right_families = {tuple(family) for family in right["compatible_strict_minimal_families"]}
    shared_families = left_families & right_families
    return {
        "known_decision_contradiction_masks": contradictions,
        "unresolved_comparison_masks": unresolved,
        "truth_vectors_certified_different": bool(contradictions),
        "truth_vectors_certified_equal": not contradictions and not unresolved,
        "truth_vectors_equality_unresolved": not contradictions and bool(unresolved),
        "families_certified_different": not shared_families,
        "families_certified_equal": len(left_families) == len(right_families) == 1
        and bool(shared_families),
        "family_equality_unresolved": bool(shared_families)
        and not (len(left_families) == len(right_families) == 1),
        "shared_compatible_families": [list(family) for family in sorted(shared_families)],
    }


def extract(item: dict) -> dict:
    if tuple(item["unit_ids"]) != UNITS:
        raise ValueError("h4rm3l vocabulary differs from the fixed three source units")
    decisions = {}
    original_states = {}
    for row in item["subset_decisions"]:
        selected = tuple(row["selected_unit_ids"])
        if len(selected) != len(set(selected)) or set(selected) - set(UNITS):
            raise ValueError("invalid or repeated source unit")
        mask = sum(1 << UNITS.index(unit) for unit in selected)
        if mask in decisions:
            raise ValueError("duplicate subset decision")
        if row["status"] not in STATUS_VALUE:
            raise ValueError("unrecognized status")
        decisions[mask] = STATUS_VALUE[row["status"]]
        original_states[mask] = row["status"]
    if set(decisions) != set(range(8)):
        raise ValueError("a complete table with explicit unresolved rows is required")
    result = characterize(tuple(decisions[mask] for mask in range(8)))
    stored_minima = {
        sum(1 << UNITS.index(unit) for unit in subset) for subset in item["minimal_sets"]
    }
    if stored_minima != set(result["necessary_strict_minimum_masks"]):
        raise ValueError("stored official strict minima did not reconstruct")
    return {
        "instance_id": item["instance_id"],
        "payload_sha256": item["payload_sha256"],
        "original_status_mask_order": [original_states[mask] for mask in range(8)],
        **result,
    }


def summarize(rows: list[dict]) -> dict:
    if not rows or len({row["payload_sha256"] for row in rows}) != len(rows):
        raise ValueError("expected one h4rm3l instance per distinct existing payload")
    pairs = []
    for left, right in itertools.combinations(rows, 2):
        pairs.append(
            {
                "left_instance_id": left["instance_id"],
                "right_instance_id": right["instance_id"],
                **compare(left, right),
            }
        )
    classes = defaultdict(list)
    for row in rows:
        if row["complete_binary"]:
            classes[tuple(row["truth_vector_mask_order"])].append(row["instance_id"])
    necessary_common = set(rows[0]["necessary_strict_minimum_masks"])
    possible_common = set(rows[0]["possible_strict_minimum_masks"])
    for row in rows[1:]:
        necessary_common.intersection_update(row["necessary_strict_minimum_masks"])
        possible_common.intersection_update(row["possible_strict_minimum_masks"])
    known_rows = sum(value is not None for row in rows for value in row["truth_vector_mask_order"])
    errors = sum(len(row["fixed_macro_only_explanation_known_contradiction_masks"]) for row in rows)
    lower = sum(row["minimum_recovery_cardinality_completion_bounds"][0] for row in rows)
    upper = sum(row["minimum_recovery_cardinality_completion_bounds"][1] for row in rows)
    return {
        "instance_count": len(rows),
        "unique_payload_count": len(rows),
        "logical_subset_rows": 8 * len(rows),
        "known_binary_rows": known_rows,
        "unresolved_rows": 8 * len(rows) - known_rows,
        "complete_binary_table_count": sum(row["complete_binary"] for row in rows),
        "identified_family_count": sum(row["family_identified"] for row in rows),
        "necessary_minimum_occurrences": sum(
            len(row["necessary_strict_minimum_masks"]) for row in rows
        ),
        "possible_minimum_occurrences": sum(
            len(row["possible_strict_minimum_masks"]) for row in rows
        ),
        "complete_binary_truth_vector_class_count": len(classes),
        "complete_binary_truth_vector_classes": [
            {"truth_vector_mask_order": list(vector), "instance_ids": ids}
            for vector, ids in sorted(classes.items())
        ],
        "common_certified_strict_minimum_masks_across_every_instance": sorted(necessary_common),
        "common_possible_strict_minimum_masks_across_every_instance": sorted(possible_common),
        "common_known_recovery_masks_across_every_instance": [
            mask
            for mask in range(8)
            if all(row["truth_vector_mask_order"][mask] == 1 for row in rows)
        ],
        "pairwise": {
            "pair_count": len(pairs),
            **{
                key: sum(pair[key] for pair in pairs)
                for key in (
                    "truth_vectors_certified_different",
                    "truth_vectors_certified_equal",
                    "truth_vectors_equality_unresolved",
                    "families_certified_different",
                    "families_certified_equal",
                    "family_equality_unresolved",
                )
            },
            "known_contradiction_mask_occurrences": sum(
                len(pair["known_decision_contradiction_masks"]) for pair in pairs
            ),
            "comparisons_are_not_independent_samples": True,
        },
        "fixed_existing_macro_baseline": {
            "macro_mask": 3,
            "selection": "PREVIOUSLY_DECLARED_G0_NOT_SELECTED_BY_THIS_AUDIT",
            "is_fresh_or_out_of_sample": False,
            "recovery_successes": sum(row["fixed_macro_status"] == 1 for row in rows),
            "recovery_failures": sum(row["fixed_macro_status"] == 0 for row in rows),
            "recovery_unknowns": sum(row["fixed_macro_status"] is None for row in rows),
            "strict_minimality_counts": dict(
                Counter(row["fixed_macro_strict_minimality"] for row in rows)
            ),
            "all_instances_share_coarse_truth_vector": len(
                {tuple(row["coarse_truth_vector"]) for row in rows}
            )
            == 1,
            "stronger_macro_only_explanation_prediction": "RECOVERED iff mask contains G0",
            "stronger_explanation_known_errors": errors,
            "stronger_explanation_known_matches": known_rows - errors,
            "stronger_explanation_unknown_decisions": 8 * len(rows) - known_rows,
            "stronger_explanation_instances_with_known_error": sum(
                bool(row["fixed_macro_only_explanation_known_contradiction_masks"]) for row in rows
            ),
            "fixed_macro_total_removed_unit_count": 2 * len(rows),
            "oracle_minimum_total_removed_unit_completion_bounds": [lower, upper],
            "oracle_unit_saving_completion_bounds": [2 * len(rows) - upper, 2 * len(rows) - lower],
            "unit_counts_are_not_token_cost_or_preserved_utility": True,
            "baseline_is_not_claimed_to_explain_all_subsets": True,
        },
        "per_payload_pair": pairs,
    }


def run(root: Path) -> dict:
    source = root / SOURCE
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("frozen safe D3 source identity mismatch")
    items = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    if len(items) != 12:
        raise ValueError("unexpected original D3 denominator")
    rows = [extract(item) for item in items if item["attack_family"] == "h4rm3l"]
    if len(rows) != 9:
        raise ValueError("unexpected h4rm3l denominator")
    result = {
        "schema_version": "jbspan-pa-structural-reentry-audit-v1",
        "evidence_class": "RETROSPECTIVE_EXPLORATORY_ORIGINAL_TOPIC_REENTRY_NOT_CONFIRMATION",
        "status": "AUDIT_COMPLETE_NO_PAPER_SUCCESS_GATE",
        "source": {"path": SOURCE, "sha256": SOURCE_SHA256},
        "analysis_sha256": {SCRIPT: sha256(root / SCRIPT)},
        "scope": {
            "new_target_calls": 0,
            "new_judge_calls": 0,
            "raw_content_read": False,
            "primary_a_opened": False,
            "reserve_b_opened": False,
            "d3_or_c1n_reclassified": False,
            "source_instances_excluded_from_h4rm3l": 0,
        },
        "vocabulary": {"unit_ids": list(UNITS), "mask_rule": "bit i selects unit_ids[i]"},
        "interpretation": {
            "estimand": "Frozen intervention-vocabulary/model/seed/evaluator-relative recovery.",
            "payload_conditioning": (
                "Observed distinct existing payload tables, not causal isolation of payload "
                "semantics from model or evaluator variability."
            ),
            "unknown": "Unresolved rows are arbitrary completions, not negatives or human truth.",
            "completion_bounds": "Finite identification bounds, not confidence intervals.",
            "replication": "Nine development payloads, one target; rows/pairs are not replicates.",
            "macro": (
                "A universal working intervention need not explain every alternative recovery. "
                "Its success is not defeated by a diagnostic explanation mismatch."
            ),
            "one_path": "No all-family recall comparison alleges a one-path guarantee error.",
            "novelty": "Profile diversity alone neither establishes novelty nor ICLR suitability.",
            "remaining_hypothesis": (
                "Stable payload-conditioned fine-scale recovery profiles may survive the same "
                "coarse repair; this needs fresh model/seed/measurement validation and an "
                "analysis consequence beyond enumerating additional sets."
            ),
        },
        "summary": summarize(rows),
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
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise ValueError("write-once output already exists with different content")
    else:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    summary = {key: value for key, value in result["summary"].items() if key != "per_payload_pair"}
    print(
        json.dumps(
            {"summary": summary, "result_identity_sha256": result["result_identity_sha256"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
