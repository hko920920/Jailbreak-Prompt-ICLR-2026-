"""Exact retrospective common-order audit of one hash-pinned SAFE P/A table.

No inference, network, private data, or source-artifact modification. UNKNOWN
labels are ignored for the known-cell fit and exhaustively completed only for
explicit sensitivity bounds. A shared arbitrary intervention score and a
separate threshold for every payload define the fitted deterministic family.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from pathlib import Path

SOURCE = "data/natural_language_localization/pa_structural_reentry_v1/audit.safe.json"
SOURCE_SHA256 = "94cbaefbc2a923e8ee0fe050a1cb4cde023e184a85c0636f17448c096e25c636"
SCRIPT = "scripts/audit_pa_common_order_v1.py"
OUTPUT = "data/natural_language_localization/pa_common_order_v1/audit.safe.json"
SOURCE_SCHEMA = "jbspan-pa-structural-reentry-audit-v1"
MAX_SOURCE_BYTES = 1_000_000
MAX_UNKNOWNS = 8
STATUS_VALUE = {
    "RECOVERED": 1,
    "NOT_RECOVERED": 0,
    "ABSTAINED": None,
    "CAPABILITY_CONFOUNDED": None,
    "UNKNOWN": None,
}


def validate_matrix(matrix: tuple[tuple[int | None, ...], ...]) -> int:
    if not matrix or len(matrix) > 100:
        raise ValueError("matrix must have 1 to 100 rows")
    width = len(matrix[0])
    if not 1 <= width <= 8 or any(len(row) != width for row in matrix):
        raise ValueError("matrix must be rectangular with 1 to 8 columns")
    if any(
        value is not None and (type(value) is not int or value not in (0, 1))
        for row in matrix
        for value in row
    ):
        raise ValueError("labels must be integer 0, integer 1, or None")
    return width


def threshold_fit(row: tuple[int | None, ...], order: tuple[int, ...]) -> tuple[int, int]:
    """Return minimum known-label errors and first minimizing split index.

    The order is low-to-high score. Before split k predict 0; at/after k
    predict 1. k=0 and k=width include constant rows. Score ties need not be
    enumerated: every tied-score threshold table has a strict-order refinement.
    """
    cost = sum(value == 0 for value in row)
    best, split = cost, 0
    for position, mask in enumerate(order, start=1):
        value = row[mask]
        if value is not None:
            cost += 1 if value else -1
        if cost < best:
            best, split = cost, position
    return best, split


def common_order_fit(matrix: tuple[tuple[int | None, ...], ...]) -> dict:
    width = validate_matrix(matrix)
    best_error = len(matrix) * width + 1
    best_order: tuple[int, ...] = ()
    best_splits: tuple[int, ...] = ()
    optimal_orders = 0
    evaluated = 0
    for order in itertools.permutations(range(width)):
        fits = tuple(threshold_fit(row, order) for row in matrix)
        error = sum(fit[0] for fit in fits)
        evaluated += 1
        if error < best_error:
            best_error = error
            best_order = order
            best_splits = tuple(fit[1] for fit in fits)
            optimal_orders = 1
        elif error == best_error:
            optimal_orders += 1
    errors = []
    unknown_predictions = []
    for row_index, (row, split) in enumerate(zip(matrix, best_splits, strict=True)):
        for rank, mask in enumerate(best_order):
            predicted = int(rank >= split)
            value = row[mask]
            cell = {"row_index": row_index, "mask_id": mask, "prediction": predicted}
            if value is None:
                unknown_predictions.append(cell)
            elif predicted != value:
                errors.append({**cell, "observed_label": value})
    if len(errors) != best_error or evaluated != math.factorial(width):
        raise AssertionError("exact search consistency failure")
    return {
        "minimum_label_error_count": best_error,
        "orders_evaluated": evaluated,
        "optimal_order_count": optimal_orders,
        "lexicographically_first_optimal_low_to_high_mask_order": list(best_order),
        "first_optimal_split_index_by_row": list(best_splits),
        "one_optimal_fit_known_label_errors": errors,
        "one_optimal_fit_unknown_predictions_not_observations": unknown_predictions,
    }


def strict_crossovers(matrix: tuple[tuple[int | None, ...], ...]) -> dict:
    width = validate_matrix(matrix)
    witnesses = []
    fully_observed = 0
    eligible_rows = set()
    eligible_masks = set()
    cells: Counter = Counter()
    for left, right in itertools.combinations(range(len(matrix)), 2):
        for first, second in itertools.combinations(range(width), 2):
            labels = (
                matrix[left][first], matrix[left][second],
                matrix[right][first], matrix[right][second],
            )
            if None in labels:
                continue
            fully_observed += 1
            if labels not in ((1, 0, 0, 1), (0, 1, 1, 0)):
                continue
            witnesses.append({
                "row_indices": [left, right],
                "mask_ids": [first, second],
                "labels_row_major": list(labels),
            })
            eligible_rows.add((left, right))
            eligible_masks.add((first, second))
            for row_index in (left, right):
                for mask in (first, second):
                    cells[row_index, mask] += 1
    return {
        "candidate_row_pair_mask_pair_count": math.comb(len(matrix), 2)
        * math.comb(width, 2),
        "fully_observed_row_pair_mask_pair_count": fully_observed,
        "strict_crossover_count": len(witnesses),
        "distinct_row_pairs_with_strict_crossover": len(eligible_rows),
        "distinct_mask_pairs_with_strict_crossover": len(eligible_masks),
        "witnesses": witnesses,
        "cell_witness_multiplicity": [
            {"row_index": row, "mask_id": mask, "witness_count": count}
            for (row, mask), count in sorted(cells.items())
        ],
        "interpretation": "Witnesses may share cells and are not independent samples.",
    }


def analyze(matrix: tuple[tuple[int | None, ...], ...]) -> dict:
    width = validate_matrix(matrix)
    unknown = [
        (row_index, mask)
        for row_index, row in enumerate(matrix)
        for mask, value in enumerate(row)
        if value is None
    ]
    if len(unknown) > MAX_UNKNOWNS:
        raise ValueError("UNKNOWN completion search exceeds the bounded audit limit")
    known_fit = common_order_fit(matrix)
    completion_results = []
    for assignment in itertools.product((0, 1), repeat=len(unknown)):
        completed = [list(row) for row in matrix]
        for (row_index, mask), value in zip(unknown, assignment, strict=True):
            completed[row_index][mask] = value
        complete_matrix = tuple(tuple(row) for row in completed)
        fit = common_order_fit(complete_matrix) if unknown else known_fit
        crossovers = strict_crossovers(complete_matrix)
        completion_results.append({
            "assigned_unknown_values_in_declared_order": list(assignment),
            "minimum_label_error_count": fit["minimum_label_error_count"],
            "optimal_order_count": fit["optimal_order_count"],
            "strict_crossover_count": crossovers["strict_crossover_count"],
        })
    minimum = min(item["minimum_label_error_count"] for item in completion_results)
    maximum = max(item["minimum_label_error_count"] for item in completion_results)
    if minimum != known_fit["minimum_label_error_count"]:
        raise AssertionError("optimistic completion must equal ignored-UNKNOWN optimum")
    known_count = len(matrix) * width - len(unknown)
    return {
        "row_count": len(matrix),
        "mask_count": width,
        "known_cell_count": known_count,
        "unknown_cell_count": len(unknown),
        "known_fit": known_fit,
        "observed_crossovers": strict_crossovers(matrix),
        "unknown_sensitivity": {
            "unknown_cells_in_assignment_order": [
                {"row_index": row_index, "mask_id": mask} for row_index, mask in unknown
            ],
            "completion_count": len(completion_results),
            "full_table_reoptimized_error_bounds": [minimum, maximum],
            "completion_results": completion_results,
            "definition": (
                "Min/max of the exact best common-order error over all binary UNKNOWN "
                "completions, with order and per-row thresholds refit for each completion. "
                "Assignments are sensitivity cases, never new observed labels."
            ),
        },
        "known_table_common_order_incompatible": minimum > 0,
        "statistical_rejection_claimed": False,
        "finite_error_distance_interpretation": (
            "Minimum number of known binary cell labels that must be changed to fit "
            "some shared arbitrary intervention order plus per-P thresholds. This is "
            "not an estimated evaluator error rate or a statistical confidence bound."
        ),
    }


def contained_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("artifact path escapes the selected root")
    return path


def read_source(root: Path) -> tuple[list[dict], dict]:
    path = contained_path(root, SOURCE)
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("SAFE source exceeds the byte bound")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("SAFE source hash mismatch")
    source = json.loads(raw.decode("utf-8"))
    if source.get("schema_version") != SOURCE_SCHEMA:
        raise ValueError("unexpected SAFE source schema")
    rows = source.get("per_instance")
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("expected all nine SAFE source instances without selection")
    projected = []
    for row in rows:
        for name in ("instance_id", "payload_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", row.get(name, "")):
                raise ValueError("unsafe or malformed source identifier")
        values = row.get("truth_vector_mask_order")
        if not isinstance(values, list) or len(values) != 8:
            raise ValueError("expected all eight masks in declared order")
        statuses = row.get("original_status_mask_order")
        if not isinstance(statuses, list) or len(statuses) != 8:
            raise ValueError("missing original status vector")
        if any(
            status not in STATUS_VALUE or STATUS_VALUE[status] != value
            for status, value in zip(statuses, values, strict=True)
        ):
            raise ValueError("original status and binary/UNKNOWN label disagree")
        projected.append({
            "instance_id": row["instance_id"],
            "payload_sha256": row["payload_sha256"],
            "truth_vector_mask_order": values,
        })
    for key in ("instance_id", "payload_sha256"):
        if len({row[key] for row in projected}) != len(projected):
            raise ValueError("source identifiers must be distinct")
    matrix = tuple(tuple(row["truth_vector_mask_order"]) for row in projected)
    validate_matrix(matrix)
    if sum(value is None for row in matrix for value in row) != 2:
        raise ValueError("expected the two original UNKNOWN labels")
    return projected, {"path": SOURCE, "sha256": SOURCE_SHA256, "size_bytes": len(raw)}


def build_report(root: Path) -> dict:
    rows, source = read_source(root)
    matrix = tuple(tuple(row["truth_vector_mask_order"]) for row in rows)
    report = {
        "schema_version": "jbspan-pa-common-order-audit-v1",
        "evidence_class": "RETROSPECTIVE_EXPLORATORY_DERIVATION_NOT_CONFIRMATION",
        "status": "AUDIT_COMPLETE_NO_SCIENTIFIC_PASS_GATE",
        "source": source,
        "analysis_sha256": hashlib.sha256(contained_path(root, SCRIPT).read_bytes()).hexdigest(),
        "scope": {
            "new_target_calls": 0,
            "new_judge_calls": 0,
            "raw_content_read": False,
            "primary_a_opened": False,
            "reserve_b_opened": False,
            "old_verdicts_reclassified": False,
            "source_instances_excluded": 0,
        },
        "null_model": {
            "definition": "R_p(S) = 1[shared_score(S) >= payload_threshold(p)]",
            "shared_score_arbitrary_over_all_masks": True,
            "payload_specific_thresholds_unrestricted": True,
            "subset_monotonicity_assumed": False,
            "unit_additivity_assumed": False,
            "observed_label_noise_modeled": False,
            "order_direction": "low shared recovery score to high shared recovery score",
        },
        "rows_in_declared_order": rows,
        "analysis": analyze(matrix),
        "interpretation_limits": [
            "All rows are already observed development data; no held-out confirmation.",
            "One finite crossover does not establish stable semantic payload causality.",
            "Seed, evaluator, and P-associated rendering variation remain alternatives.",
            "Pairwise witnesses and table cells are not independent sample units.",
            "Common coarse repair success is unchanged and no defense superiority is inferred.",
            "UNKNOWN assignments are bounded sensitivity calculations, not observations.",
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    report["result_identity_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return report


def write_once(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-output", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.write_output and contained_path(root, OUTPUT).exists():
        raise FileExistsError("write-once audit output already exists")
    report = build_report(root)
    if args.write_output:
        write_once(contained_path(root, OUTPUT), report)
    analysis = report["analysis"]
    print(json.dumps({
        "status": report["status"],
        "source_sha256": SOURCE_SHA256,
        "known_cells": analysis["known_cell_count"],
        "unknown_cells": analysis["unknown_cell_count"],
        "strict_crossovers": analysis["observed_crossovers"]["strict_crossover_count"],
        "minimum_common_order_known_errors": analysis["known_fit"]["minimum_label_error_count"],
        "full_table_completion_error_bounds": analysis["unknown_sensitivity"][
            "full_table_reoptimized_error_bounds"
        ],
        "orders_evaluated_per_fit": analysis["known_fit"]["orders_evaluated"],
        "result_identity_sha256": report["result_identity_sha256"],
        "output_written": OUTPUT if args.write_output else None,
    }, indent=2))


if __name__ == "__main__":
    main()
