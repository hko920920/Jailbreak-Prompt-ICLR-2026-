"""Independent Stage7 SAFE arithmetic audit; no production calculation imports.

The fit uses precomputed zero-prefix subset costs, not the production incremental
threshold scan. Default CLI is read-only. Optional write-once publication needs
the completed, externally pinned Stage7 proof and the same live Stage7 direction.
Neither a numeric match nor this SAFE report re-certifies private raw evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

EXECUTION = "1f720cab7e9678278e52542cf0ee33e791d9b2e331c4a2b7cb1b25f64e980ab2"
DIRECTION = "0b8d4267de2b18e289c570903c0233559ba4ee5ad7bc855e2acf56bccbdf6d70"
WRAPPER = "4ebb22e1055a69e0c5b441a28ed36cb52a4910ba3f0a6b585c6b4418fd32b1f9"
REFERENCE = "fd6334ff91f88137cd88586be3aec67e7e49910d07d3cca0430eeabf72e157f8"
SCRIPT = "scripts/audit_pa_stage7_numeric_v2.py"
TEST = "tests/test_pa_stage7_numeric_v2.py"
BASE = f"data/natural_language_localization/pa_reentry_v2/{EXECUTION}/finalization"
RUNTIME = "docs/PA_STAGE7_RUNTIME_2026-09-07_V2"
REPORT_BASE = f"data/natural_language_localization/pa_stage7_numeric_audit_v2/{EXECUTION}"
STAGE6_PINS = {
    "measurements.safe.json": "b9ce483fbb633d5bd533190f1d7b2324c45caedd16ed3e83f69d324fbdb41ac1",
    "result.safe.json": "b427c21a70700d7ad0995df48b7d79a378e374d629ff8f1b0716c204b747eda3",
    "verification.safe.json": "c4f91f03091b5a9675de8594e275a92ee786c5fec41cb875a2d7ecf68086cf1f",
}
POSITIONS = (0, 3, 4, 10, 11, 14, 15, 16, 18, 21, 22, 23, 24, 25, 33, 34, 36, 37, 42, 43, 44)
OPS = ("SOURCE_AWARE_OMIT", "LAYOUT_PRESERVING_BLANK")
SEEDS = (11, 23, 47)
LABELS = {
    "RECOVERED": 1,
    "NOT_RECOVERED": 0,
    **dict.fromkeys(
        (
            "ABSTAINED",
            "CAPABILITY_CONFOUNDED",
            "INVALID_INTERVENTION",
            "TRUNCATED",
            "INCOMPLETE",
            "UNKNOWN",
        )
    ),
}
FAILURES = ["DISK_FREE_SPACE_BELOW_15_GIB", "CONTINUATION_PRELAUNCH_DISK_BELOW_20_GIB"]
SHA = re.compile(r"[0-9a-f]{64}")
_PREFIXES = {}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(canonical(value))


def sealed(value, field="result_identity_sha256"):
    require(
        isinstance(value, dict)
        and value.get(field) == digest({k: v for k, v in value.items() if k != field}),
        "NUMERIC_BAD_SEAL",
    )
    return value


def stamp(value):
    require(isinstance(value, str), "NUMERIC_TIME_TYPE")
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(moment.utcoffset() == timedelta(0), "NUMERIC_TIME_NOT_UTC")
    return moment


def valid_matrix(matrix):
    require(isinstance(matrix, (tuple, list)) and 1 <= len(matrix) <= 45, "NUMERIC_MATRIX_HEIGHT")
    width = len(matrix[0])
    require(1 <= width <= 8 and all(len(row) == width for row in matrix), "NUMERIC_MATRIX_WIDTH")
    require(
        all(x is None or type(x) is int and x in (0, 1) for row in matrix for x in row),
        "NUMERIC_MATRIX_LABEL",
    )
    return width


def prefix_sets(width):
    if width not in _PREFIXES:
        orders = np.array(list(itertools.permutations(range(width))), dtype=np.int8)
        bits = np.left_shift(np.int16(1), orders)
        subsets = np.concatenate(
            (np.zeros((len(orders), 1), dtype=np.int16), np.bitwise_or.accumulate(bits, axis=1)),
            axis=1,
        )
        _PREFIXES[width] = orders, subsets
    return _PREFIXES[width]


def fit(matrix):
    """Exact arbitrary common order/per-row cut fit using independent subset costs."""
    width = valid_matrix(matrix)
    orders, subsets = prefix_sets(width)
    totals = np.zeros(len(orders), dtype=np.int16)
    costs = []
    for row in matrix:
        delta = [0 if x is None else 1 if x == 1 else -1 for x in row]
        cost = np.empty(1 << width, dtype=np.int16)
        cost[0] = row.count(0)
        for subset in range(1, 1 << width):
            bit = subset & -subset
            cost[subset] = cost[subset ^ bit] + delta[bit.bit_length() - 1]
        totals += cost[subsets].min(axis=1)
        costs.append(cost)
    minimum = int(totals.min())
    optima = np.flatnonzero(totals == minimum)
    chosen = int(optima[0])
    order = list(map(int, orders[chosen]))
    splits, errors, unknown_predictions = [], [], []
    for index, (row, cost) in enumerate(zip(matrix, costs, strict=True)):
        split = int(np.argmin(cost[subsets[chosen]]))
        splits.append(split)
        for rank, mask in enumerate(order):
            prediction = int(rank >= split)
            cell = {"row_index": index, "mask_id": mask, "prediction": prediction}
            if row[mask] is None:
                unknown_predictions.append(cell)
            elif row[mask] != prediction:
                errors.append({**cell, "observed_label": row[mask]})
    require(len(errors) == minimum, "NUMERIC_FIT_ACCOUNTING")
    return {
        "minimum_label_error_count": minimum,
        "orders_evaluated": len(orders),
        "optimal_order_count": len(optima),
        "lexicographically_first_optimal_low_to_high_mask_order": order,
        "first_optimal_split_index_by_row": splits,
        "one_optimal_fit_known_label_errors": errors,
        "one_optimal_fit_unknown_predictions_not_observations": unknown_predictions,
    }


def literal_fit(matrix):
    """Small synthetic oracle: explicitly construct every cut's predictions."""
    width = valid_matrix(matrix)
    require(width <= 3, "NUMERIC_LITERAL_ORACLE_BOUND")
    candidates = []
    for order in itertools.permutations(range(width)):
        rows = []
        for row in matrix:
            losses = []
            for cut in range(width + 1):
                predicted = {mask: int(rank >= cut) for rank, mask in enumerate(order)}
                losses.append(
                    sum(x is not None and x != predicted[mask] for mask, x in enumerate(row))
                )
            rows.append((min(losses), losses.index(min(losses))))
        candidates.append((sum(x[0] for x in rows), list(order), [x[1] for x in rows]))
    minimum = min(x[0] for x in candidates)
    best = [x for x in candidates if x[0] == minimum]
    return minimum, len(best), best[0][1], best[0][2]


def synthetic_self_check():
    count = 0
    for width, domain in ((2, (0, 1, None)), (3, (0, 1))):
        for flat in itertools.product(domain, repeat=width * 2):
            actual = fit([list(flat[:width]), list(flat[width:])])
            expected = literal_fit([list(flat[:width]), list(flat[width:])])
            require(
                (
                    actual["minimum_label_error_count"],
                    actual["optimal_order_count"],
                    actual["lexicographically_first_optimal_low_to_high_mask_order"],
                    actual["first_optimal_split_index_by_row"],
                )
                == expected,
                "NUMERIC_SYNTHETIC_ORACLE_MISMATCH",
            )
            count += 1
    require(count == 145, "NUMERIC_SYNTHETIC_CASE_COUNT")
    return count


def crossovers(matrix):
    width = valid_matrix(matrix)
    witnesses, fully = [], 0
    row_pairs, mask_pairs, cells = set(), set(), Counter()
    for left, right in itertools.combinations(range(len(matrix)), 2):
        for first, second in itertools.combinations(range(width), 2):
            values = (
                matrix[left][first],
                matrix[left][second],
                matrix[right][first],
                matrix[right][second],
            )
            if any(x is None for x in values):
                continue
            fully += 1
            if values in ((1, 0, 0, 1), (0, 1, 1, 0)):
                witnesses.append(
                    {
                        "row_indices": [left, right],
                        "mask_ids": [first, second],
                        "labels_row_major": list(values),
                    }
                )
                row_pairs.add((left, right))
                mask_pairs.add((first, second))
                cells.update(itertools.product((left, right), (first, second)))
    return {
        "candidate_row_pair_mask_pair_count": math.comb(len(matrix), 2) * math.comb(width, 2),
        "fully_observed_row_pair_mask_pair_count": fully,
        "strict_crossover_count": len(witnesses),
        "distinct_row_pairs_with_strict_crossover": len(row_pairs),
        "distinct_mask_pairs_with_strict_crossover": len(mask_pairs),
        "witnesses": witnesses,
        "cell_witness_multiplicity": [
            {"row_index": r, "mask_id": k, "witness_count": n}
            for (r, k), n in sorted(cells.items())
        ],
    }


def shared_crossovers(six, positions):
    require(len(six) == 6, "NUMERIC_EXACT_SIX_REQUIRED")
    sets = [
        {
            (tuple(w["row_indices"]), tuple(w["mask_ids"]), tuple(w["labels_row_major"]))
            for w in value["witnesses"]
        }
        for value in six
    ]
    common = set.intersection(*sets)
    witnesses, cells = [], Counter()
    for rows, masks, values in sorted(common):
        payloads = [positions[index] for index in rows]
        witnesses.append(
            {
                "payload_positions": payloads,
                "mask_ids": list(masks),
                "labels_row_major": list(values),
                "matching_slice_count": 6,
            }
        )
        cells.update(itertools.product(payloads, masks))
    return {
        "required_slice_count": 6,
        "same_orientation_required": True,
        "strict_shared_crossover_count": len(witnesses),
        "witnesses": witnesses,
        "distinct_involved_cells": len(cells),
        "maximum_witnesses_sharing_one_cell": max(cells.values(), default=0),
        "cell_witness_multiplicity": [
            {"payload_position": p, "mask_id": k, "witness_count": n}
            for (p, k), n in sorted(cells.items())
        ],
        "independent_replicate_or_statistical_significance_claimed": False,
    }


def matrix_inputs(measured, positions):
    require(
        list(positions) == sorted(set(positions)) and 1 <= len(positions) <= 45,
        "NUMERIC_POPULATION",
    )
    table = measured["tables"]
    primary = {(x["payload_position"], x["mask_id"]): x for x in table["primary_rows"]}
    require(
        len(primary) == len(table["primary_rows"]) == len(positions) * 8
        and set(primary) == set(itertools.product(positions, range(8))),
        "NUMERIC_PRIMARY_FRAME",
    )
    matrices = {"primary": [[LABELS[primary[p, k]["status"]] for k in range(8)] for p in positions]}
    mappings = {}
    for group, name in (("ordinary", "slice_rows"), ("qualified", "control_qualified_slice_rows")):
        mapping = {
            (x["payload_position"], x["mask_id"], x["neutralizer_id"], x["seed"]): x
            for x in table[name]
        }
        require(
            len(mapping) == len(table[name]) == len(positions) * 48
            and set(mapping) == set(itertools.product(positions, range(8), OPS, SEEDS)),
            "NUMERIC_COMPLETE_SLICE_FRAME",
        )
        for row in mapping.values():
            require(
                (row["label"] is None or type(row["label"]) is int and row["label"] in (0, 1))
                and row["status"] in LABELS
                and LABELS[row["status"]] == row["label"],
                "NUMERIC_LABEL_STATUS",
            )
        mappings[group] = mapping
        for operator, seed in itertools.product(OPS, SEEDS):
            matrices[f"{group}:{operator}:{seed}"] = [
                [mapping[p, k, operator, seed]["label"] for k in range(8)] for p in positions
            ]
        matrices[group + ":uniform"] = [
            [
                values[0] if all(x == values[0] for x in values) else None
                for values in (
                    [mapping[p, k, op, seed]["label"] for op, seed in itertools.product(OPS, SEEDS)]
                    for k in range(8)
                )
            ]
            for p in positions
        ]
    for key, row in mappings["qualified"].items():
        controls = row["matched_controls_passed"]
        require(
            (key[1] == 0 and controls is None and row["label"] == 0)
            or (
                key[1] != 0
                and type(controls) is bool
                and row["label"] == (mappings["ordinary"][key]["label"] if controls else None)
            ),
            "NUMERIC_QUALIFIED_FILTER",
        )
    for p, k in itertools.product(positions, range(8)):
        values = [
            mappings["ordinary"][p, k, op, seed]["label"]
            for op, seed in itertools.product(OPS, SEEDS)
        ]
        label = LABELS[primary[p, k]["status"]]
        require(
            (label == 1) == (values == [1] * 6)
            and (label != 0 or 0 in values)
            and (k != 0 or label == 0 and values == [0] * 6),
            "NUMERIC_PRIMARY_SLICES",
        )
    normalized = {
        "schema_version": "jbspan-pa-llama-topology-analysis-input-v1",
        "screen_result_identity_sha256": table["screen_result_identity_sha256"],
        "primary_rows": [primary[key] for key in itertools.product(positions, range(8))],
    }
    for group, name in (("ordinary", "slice_rows"), ("qualified", "control_qualified_slice_rows")):
        normalized[name] = [
            mappings[group][key] for key in itertools.product(positions, range(8), OPS, SEEDS)
        ]
    return matrices, digest(normalized)


def summarize_matrix(matrix, cache):
    def cached(value):
        key = tuple(tuple(row) for row in value)
        if key not in cache:
            cache[key] = fit(value)
        return cache[key]

    fitted = cached(matrix)
    unknown = [(r, k) for r, row in enumerate(matrix) for k, x in enumerate(row) if x is None]
    distance = fitted["minimum_label_error_count"]
    lower, upper = distance, min(len(matrix) * 8, distance + len(unknown))
    completions = []
    if len(unknown) <= 2:
        for assignment in itertools.product((0, 1), repeat=len(unknown)):
            full = [list(row) for row in matrix]
            for (r, k), value in zip(unknown, assignment, strict=True):
                full[r][k] = value
            completions.append(
                {
                    "hypothetical_assignment": list(assignment),
                    "minimum_label_error_count": cached(full)["minimum_label_error_count"],
                    "assignment_is_observed": False,
                }
            )
        lower = min(row["minimum_label_error_count"] for row in completions)
        upper = max(row["minimum_label_error_count"] for row in completions)
        require(lower == distance, "NUMERIC_OPTIMISTIC_BOUND")
    lookup_error = sum(
        min(sum(row[k] == 0 for row in matrix), sum(row[k] == 1 for row in matrix))
        for k in range(8)
    )
    require(distance <= lookup_error, "NUMERIC_NESTED_LOOKUP_NULL")
    return {
        "matrix_identity_sha256": digest(matrix),
        "observed_matrix": matrix,
        "known_fit": fitted,
        "known_cell_count": len(matrix) * 8 - len(unknown),
        "unknown_cell_count": len(unknown),
        "strict_crossovers": crossovers(matrix),
        "minimum_known_cell_change_distance_to_common_order": distance,
        "p_independent_lookup_error": lookup_error,
        "unknown_sensitivity": {
            "unknown_cells": [{"row_index": r, "mask_id": k} for r, k in unknown],
            "optimistic_full_table_error_exact": distance,
            "full_table_reoptimized_error_bounds": [lower, upper],
            "upper_bound_is_sharp": len(unknown) <= 2,
            "method": "EXACT_ALL_COMPLETIONS"
            if len(unknown) <= 2
            else "LOOSE_KNOWN_ERROR_PLUS_UNKNOWNS",
            "maximum_unknowns_for_exact_enumeration": 2,
            "completion_count": len(completions),
            "hypothetical_completions": completions,
            "unknown_imputed_as_observed": False,
        },
    }


def production_matrices(analyzed):
    output = {"primary": analyzed["primary"]}
    for group, value in (("ordinary", analyzed), ("qualified", analyzed["control_qualified_c3"])):
        rows = value["neutralizer_seed_tables"]
        require(
            len(rows) == 6
            and {(r["neutralizer_id"], r["seed"]) for r in rows}
            == set(itertools.product(OPS, SEEDS)),
            "NUMERIC_PRODUCTION_SIX_TABLES",
        )
        for row in rows:
            output[f"{group}:{row['neutralizer_id']}:{row['seed']}"] = row["analysis"]
        output[group + ":uniform"] = value["all_six_uniformly_certified_cells"]
    require(len(output) == 15, "NUMERIC_PRODUCTION_FIFTEEN")
    return output


def verify_analysis(measured, analyzed, *, positions=POSITIONS):
    matrices, normalized_sha = matrix_inputs(measured, positions)
    require(
        analyzed["all_stable_payload_positions"] == list(positions)
        and analyzed["selected_payload_denominator"] == len(positions)
        and analyzed["normalized_analysis_input_identity_sha256"] == normalized_sha
        and analyzed["control_qualified_frame_supplied"] is True
        and analyzed["reference_code_sha256"] == REFERENCE,
        "NUMERIC_ANALYSIS_INPUT_BINDING",
    )
    require(
        analyzed["evidence_class"] == "RESULT_INFORMED_EXPOSED_DEVELOPMENT_NOT_CONFIRMATION"
        and all(
            analyzed[key] is False
            for key in (
                "execution_authorized",
                "topology_authorized",
                "paper_validity",
                "scientific_measurement_reverified",
                "statistical_rejection_claimed",
                "payload_semantic_causality_claimed",
            )
        )
        and all(
            type(analyzed[key]) is int and analyzed[key] == 0
            for key in ("new_model_calls", "historical_private_reads", "sealed_reads")
        ),
        "NUMERIC_ANALYSIS_CLAIM_CHANGED",
    )
    observed = production_matrices(analyzed)
    cache, expected, shared = {}, {}, {}
    for name, matrix in matrices.items():
        result = summarize_matrix(matrix, cache)
        actual = observed[name]
        for key in (
            "observed_matrix",
            "known_fit",
            "known_cell_count",
            "unknown_cell_count",
            "minimum_known_cell_change_distance_to_common_order",
            "unknown_sensitivity",
        ):
            require(
                canonical(actual[key]) == canonical(result[key]),
                "NUMERIC_MATRIX_COMPARISON_MISMATCH",
            )
        require(
            all(
                canonical(actual["strict_crossovers"].get(k)) == canonical(v)
                for k, v in result["strict_crossovers"].items()
            ),
            "NUMERIC_CROSSOVER_MISMATCH",
        )
        require(
            actual["p_independent_lookup"]["minimum_known_label_error_count"]
            == result["p_independent_lookup_error"],
            "NUMERIC_LOOKUP_MISMATCH",
        )
        require(
            actual["common_order_incompatible_with_known_labels"]
            is (result["known_fit"]["minimum_label_error_count"] > 0)
            and actual["statistical_rejection_claimed"] is False
            and actual["out_of_sample_prediction_claimed"] is False
            and actual["independent_witness_count_claimed"] is False,
            "NUMERIC_MATRIX_CLAIM_CHANGED",
        )
        expected[name] = result
    for group, actual in (("ordinary", analyzed), ("qualified", analyzed["control_qualified_c3"])):
        six = [
            expected[f"{group}:{op}:{seed}"]["strict_crossovers"]
            for op, seed in itertools.product(OPS, SEEDS)
        ]
        shared[group] = shared_crossovers(six, positions)
        require(
            canonical(shared[group]) == canonical(actual["all_six_same_oriented_crossovers"]),
            "NUMERIC_SHARED_ORIENTATION_MISMATCH",
        )
    require(analyzed["exact_fit_unique_matrix_count"] == len(cache), "NUMERIC_CACHE_COUNT")
    return {
        "matrix_count": 15,
        "unique_exact_fit_count": len(cache),
        "normalized_analysis_input_identity_sha256": normalized_sha,
        "matrices": expected,
        "shared_orientation": shared,
    }


def safe_path(root, relative, *, missing=False):
    require(
        isinstance(relative, str)
        and "\\" not in relative
        and ":" not in relative
        and all(p and p not in (".", "..") and p == p.rstrip(" .") for p in relative.split("/")),
        "NUMERIC_PATH_SCOPE",
    )
    root = Path(root).absolute()
    parts = [root, *reversed(root.parents)]
    current = root
    for part in relative.split("/"):
        current /= part
        parts.append(current)
    for path in parts:
        native = (
            Path("\\\\?\\" + str(path))
            if os.name == "nt" and not str(path).startswith("\\\\?\\")
            else path
        )
        if native.exists() or native.is_symlink():
            observed = native.lstat()
            require(
                not native.is_symlink() and not getattr(observed, "st_file_attributes", 0) & 1024,
                "NUMERIC_REPARSE",
            )
        elif not missing:
            raise ValueError("NUMERIC_INPUT_MISSING")
    return native


def read_bytes(path):
    before = path.stat()
    require(path.is_file() and before.st_size <= 32_000_000, "NUMERIC_READ_BOUND")
    raw = path.read_bytes()
    after = path.stat()
    require(
        (before.st_size, before.st_mtime_ns, before.st_ino)
        == (after.st_size, after.st_mtime_ns, after.st_ino),
        "NUMERIC_READ_RACE",
    )
    return raw


def strict_json(raw):
    def pairs(values):
        output = {}
        for key, value in values:
            require(key not in output, "NUMERIC_DUPLICATE_JSON_KEY")
            output[key] = value
        return output

    value = json.loads(raw, object_pairs_hook=pairs)
    require(raw == canonical(value) + b"\n", "NUMERIC_NONCANONICAL_INPUT")
    return value


class Snapshot:
    def __init__(self, root):
        self.root, self.files, self.directories = Path(root), {}, {}

    def read(self, relative, expected=None, *, json_value=True):
        raw = read_bytes(safe_path(self.root, relative))
        require(expected is None or sha(raw) == expected, "NUMERIC_EXTERNAL_FILE_PIN")
        require(relative not in self.files or self.files[relative] == raw, "NUMERIC_INPUT_CHANGED")
        self.files[relative] = raw
        return strict_json(raw) if json_value else raw

    def directory(self, relative, names=None):
        path = safe_path(self.root, relative)
        observed = sorted(child.name for child in path.iterdir())
        require(names is None or set(observed) == set(names), "NUMERIC_DIRECTORY_CLOSURE")
        for name in observed:
            safe_path(self.root, relative + "/" + name)
        require(not any(name.endswith(".pending") for name in observed), "NUMERIC_PENDING_INPUT")
        self.directories[relative] = observed
        return observed

    def unchanged(self):
        for relative, names in self.directories.items():
            require(
                sorted(p.name for p in safe_path(self.root, relative).iterdir()) == names,
                "NUMERIC_DIRECTORY_CHANGED",
            )
            for name in names:
                safe_path(self.root, relative + "/" + name)
        for relative, raw in self.files.items():
            require(read_bytes(safe_path(self.root, relative)) == raw, "NUMERIC_INPUT_CHANGED")

    def manifest(self):
        return [
            {"path": key, "size_bytes": len(raw), "sha256": sha(raw)}
            for key, raw in sorted(self.files.items())
        ]


def validate_direction(direction, *, now=None):
    sealed(direction, "direction_identity_sha256")
    require(
        direction["direction_identity_sha256"] == DIRECTION
        and direction["execution_identity"] == EXECUTION
        and type(direction["stage"]) is int
        and direction["stage"] == 7
        and direction["schema_version"] == "pa-reentry-postprocessing-direction-v2",
        "NUMERIC_STAGE7_DIRECTION",
    )
    issued, expires = stamp(direction["issued_at"]), stamp(direction["expires_at"])
    require(timedelta(0) < expires - issued <= timedelta(hours=2), "NUMERIC_DIRECTION_WINDOW")
    if now is not None:
        require(issued <= stamp(now) <= expires, "NUMERIC_CURRENT_DIRECTION_EXPIRED")


def load_products(root, verification_sha256):
    require(
        isinstance(verification_sha256, str) and SHA.fullmatch(verification_sha256),
        "NUMERIC_VERIFICATION_PIN_REQUIRED",
    )
    snapshot = Snapshot(root)
    old_dir, new_dir = BASE + "/measurements-only", BASE + "/with-analysis"
    names = ("measurements", "analysis", "result", "verification")
    snapshot.directory(old_dir, (*STAGE6_PINS, "publication.lock"))
    old = {
        name.removesuffix(".safe.json"): snapshot.read(old_dir + "/" + name, pin)
        for name, pin in STAGE6_PINS.items()
    }
    snapshot.directory(new_dir, (*(name + ".safe.json" for name in names), "publication.lock"))
    verification = snapshot.read(new_dir + "/verification.safe.json", verification_sha256)
    sealed(verification, "verification_identity_sha256")
    require(
        set(verification["product_file_sha256"]) == {"measurements", "analysis", "result"},
        "NUMERIC_CORE_PRODUCT_FRAME",
    )
    current = {"verification": verification}
    for name, pin in verification["product_file_sha256"].items():
        current[name] = snapshot.read(new_dir + "/" + name + ".safe.json", pin)
    for products in (old, current):
        proof = sealed(products["verification"], "verification_identity_sha256")
        require(
            proof["schema_version"] == "pa-reentry-final-verification-v2"
            and proof["actual_raw_verification_by_entrypoint"] is True
            and proof["second_continuation_execution_identity"] == EXECUTION,
            "NUMERIC_CORE_VERIFICATION",
        )
        for name, value in products.items():
            if name != "verification":
                sealed(value)
                require(
                    proof["product_identity_sha256"][name] == value["result_identity_sha256"]
                    and proof["product_file_sha256"][name] == sha(canonical(value) + b"\n"),
                    "NUMERIC_PRODUCT_JOIN",
                )
        for value in (*products.values(), products["measurements"]["tables"]):
            require(
                value["second_continuation_execution_identity"] == EXECUTION
                and value["prior_operation_failures"] == FAILURES,
                "NUMERIC_EXECUTION_DISCLOSURE",
            )
            for key in (
                "original_operational_gate_passed",
                "first_continuation_operational_gate_passed",
                "archive_relocation_contemporaneous_receipt_available",
                "original_unqualified_pass_claimed",
                "epoch_invariance_claimed",
                "paper_validity",
            ):
                require(value[key] is False, "NUMERIC_OLD_FAILURE_PROMOTED")
        table, measured, result = (
            products["measurements"]["tables"],
            products["measurements"],
            products["result"],
        )
        sealed(table)
        require(
            result["measurements_identity_sha256"] == measured["result_identity_sha256"]
            and result["table_identity_sha256"] == table["result_identity_sha256"]
            and proof["result_identity_sha256"] == result["result_identity_sha256"]
            and proof["axis_identity_sha256"] == result["axis_identity_sha256"],
            "NUMERIC_INNER_PRODUCT_JOIN",
        )
    require(
        old["result"]["analysis_complete"] is False
        and old["verification"]["analysis_complete"] is False
        and old["result"]["analysis_identity_sha256"] is None
        and current["result"]["analysis_complete"] is True
        and verification["analysis_complete"] is True,
        "NUMERIC_STAGE_BOUNDARY",
    )
    require(
        canonical(old["measurements"]) == canonical(current["measurements"])
        and old["verification"]["target_composite_proof"] == verification["target_composite_proof"]
        and old["verification"]["axis_identity_sha256"] == verification["axis_identity_sha256"],
        "NUMERIC_STAGE6_INPUTS_CHANGED",
    )
    exempt = {"analysis_complete", "analysis_identity_sha256", "result_identity_sha256"}
    require(
        {k: v for k, v in old["result"].items() if k not in exempt}
        == {k: v for k, v in current["result"].items() if k not in exempt},
        "NUMERIC_STAGE6_RESULT_DRIFT",
    )
    analyzed = current["analysis"]
    require(
        analyzed["schema_version"] == "pa-reentry-analysis-v2"
        and analyzed["result_identity_sha256"] == current["result"]["analysis_identity_sha256"]
        and analyzed["upstream_declared_topology_aggregate_identity_sha256"]
        == current["measurements"]["tables"]["result_identity_sha256"],
        "NUMERIC_ANALYSIS_LINK",
    )
    snapshot.directory(RUNTIME, ("direction.safe.json", "events", "run.lock"))
    direction = snapshot.read(RUNTIME + "/direction.safe.json")
    validate_direction(direction)
    require(verification["current_stage_direction"] == direction, "NUMERIC_CORE_DIRECTION_BIND")
    event_names = snapshot.directory(RUNTIME + "/events")
    require(
        len(event_names) == 6 and all(name.endswith(".safe.json") for name in event_names),
        "NUMERIC_STAGE7_EVENTS_REQUIRED",
    )
    events = [
        sealed(snapshot.read(RUNTIME + "/events/" + name), "identity_sha256")
        for name in event_names
    ]
    events.sort(key=lambda event: stamp(event["at"]))
    require(
        [row["event"] for row in events]
        == [
            "STAGE7_STARTED",
            "STAGE6_INPUTS_VERIFIED",
            "FROZEN_CONTEXT_LOAD_STARTED",
            "FROZEN_CONTEXT_VERIFIED",
            "ANALYSIS_FINALIZATION_STARTED",
            "STAGE7_FROZEN_ANALYSIS_COMPLETE",
        ]
        and len({row["attempt_id"] for row in events}) == 1
        and len({row["pid"] for row in events}) == 1,
        "NUMERIC_CORE_EVENT_SEQUENCE",
    )
    previous_elapsed = -1
    for event in events:
        require(
            event["schema_version"] == "pa-stage7-wrapper-event-v2"
            and event["execution_identity"] == EXECUTION
            and type(event["stage"]) is int
            and event["stage"] == 7
            and event["run_analysis"] is True
            and event["new_model_calls"] == 0
            and event["wrapper_sha256"] == WRAPPER
            and type(event["pid"]) is int
            and event["pid"] > 0
            and isinstance(event["attempt_id"], str)
            and re.fullmatch(r"[0-9a-f]{32}", event["attempt_id"])
            and type(event["elapsed_seconds"]) in (int, float)
            and math.isfinite(event["elapsed_seconds"])
            and event["elapsed_seconds"] >= previous_elapsed >= -1,
            "NUMERIC_EVENT_SCOPE",
        )
        require(event["elapsed_seconds"] >= 0, "NUMERIC_EVENT_SCOPE")
        previous_elapsed = event["elapsed_seconds"]
        validate_direction(direction, now=event["at"])
    require(
        events[0]["direction"] == direction
        and events[1]["stage6_file_sha256"] == STAGE6_PINS
        and events[-1]["verification_identity_sha256"]
        == verification["verification_identity_sha256"]
        and events[-1]["analysis_identity_sha256"] == analyzed["result_identity_sha256"]
        and events[-1]["result_identity_sha256"] == current["result"]["result_identity_sha256"]
        and events[-1]["stage6_preserved"] is True
        and events[-1]["automatic_next_stage"] is False,
        "NUMERIC_COMPLETION_EVENT_BIND",
    )
    return snapshot, current, direction


def audit(root, verification_sha256):
    snapshot, products, direction = load_products(root, verification_sha256)
    calibrations = synthetic_self_check()
    comparisons = verify_analysis(products["measurements"], products["analysis"])
    for relative in (SCRIPT, TEST):
        snapshot.read(relative, json_value=False)
    snapshot.unchanged()
    manifest = snapshot.manifest()
    report = {
        "schema_version": "pa-stage7-independent-numeric-audit-v2",
        "execution_identity": EXECUTION,
        "stage": 7,
        "direction": direction,
        "verification_file_sha256": verification_sha256,
        "core_verification_identity_sha256": products["verification"][
            "verification_identity_sha256"
        ],
        "core_analysis_identity_sha256": products["analysis"]["result_identity_sha256"],
        "source_manifest": manifest,
        "source_manifest_identity_sha256": digest(manifest),
        "comparisons_passed": True,
        "comparison": comparisons,
        "method": "EXACT_ORDER_ENUMERATION_WITH_PRECOMPUTED_ZERO_PREFIX_SUBSET_COSTS",
        "synthetic_literal_oracle_cases": calibrations,
        "numpy_version": np.__version__,
        "production_calculation_functions_called": False,
        "verification_scope": (
            "INDEPENDENT_SAFE_NUMERIC_COMPARISON_NOT_RAW_OR_OPERATIONAL_RECERTIFICATION"
        ),
        "raw_receipts_independently_reverified": False,
        "new_model_calls": 0,
        "statistical_rejection_claimed": False,
        "epoch_invariance_claimed": False,
        "original_operational_gate_passed": False,
        "first_continuation_operational_gate_passed": False,
        "prior_operation_failures": FAILURES,
        "paper_validity": False,
        "stage8_authorized": False,
        "runner_exit_independently_checked": False,
        "two_matching_input_snapshots": True,
        "input_snapshot_is_atomic": False,
    }
    report["result_identity_sha256"] = digest(report)
    return report


def publish_report(root, report, *, now=None):
    sealed(report)
    require(
        report["schema_version"] == "pa-stage7-independent-numeric-audit-v2"
        and report["execution_identity"] == EXECUTION
        and report["stage"] == 7
        and report["comparisons_passed"] is True
        and report["source_manifest_identity_sha256"] == digest(report["source_manifest"])
        and all(
            report[key] is False
            for key in (
                "raw_receipts_independently_reverified",
                "production_calculation_functions_called",
                "statistical_rejection_claimed",
                "epoch_invariance_claimed",
                "original_operational_gate_passed",
                "first_continuation_operational_gate_passed",
                "paper_validity",
                "stage8_authorized",
                "runner_exit_independently_checked",
            )
        )
        and report["new_model_calls"] == 0
        and report["prior_operation_failures"] == FAILURES,
        "NUMERIC_PUBLISH_REQUIRES_COMPARISON",
    )
    validate_direction(report["direction"], now=now or datetime.now(timezone.utc).isoformat())
    pin = report["verification_file_sha256"]
    require(isinstance(pin, str) and SHA.fullmatch(pin), "NUMERIC_OUTPUT_SCOPE")
    # Re-open only the fixed allowlisted SAFE chain and this diagnostic's source
    # immediately before publication; a report never authorizes arbitrary reads.
    snapshot, _, direction = load_products(root, pin)
    for source in (SCRIPT, TEST):
        snapshot.read(source, json_value=False)
    require(
        snapshot.manifest() == report["source_manifest"] and direction == report["direction"],
        "NUMERIC_PUBLISH_INPUT_CHANGED",
    )
    snapshot.unchanged()
    validate_direction(direction, now=now or datetime.now(timezone.utc).isoformat())
    relative = REPORT_BASE + "/" + pin + "/audit.safe.json"
    path = safe_path(root, relative, missing=True)
    raw = canonical(report) + b"\n"
    pending = safe_path(root, relative + ".pending", missing=True)
    require(not pending.exists(), "NUMERIC_PENDING_PUBLICATION_PRESERVED")
    if path.exists():
        require(read_bytes(path) == raw, "NUMERIC_REPORT_CONFLICT_PRESERVED")
        return relative, False
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive pending leaf plus exclusive hard-link publication never overwrites.
    with pending.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)
    pending.unlink()
    return relative, True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--verification-sha256", required=True)
    parser.add_argument("--write-output", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = audit(args.root, args.verification_sha256)
        location, written = (
            publish_report(args.root, report) if args.write_output else (None, False)
        )
        summary = {
            "comparisons_passed": True,
            "matrix_count": report["comparison"]["matrix_count"],
            "result_identity_sha256": report["result_identity_sha256"],
            "source_manifest_identity_sha256": report["source_manifest_identity_sha256"],
            "synthetic_literal_oracle_cases": report["synthetic_literal_oracle_cases"],
            "report_path": location,
            "report_written": written,
            "new_model_calls": 0,
            "stage8_authorized": False,
        }
        print(canonical(summary).decode())
        return 0
    except Exception as error:
        message = str(error)
        code = message if re.fullmatch(r"NUMERIC_[A-Z0-9_]+", message) else "NUMERIC_SAFE_FAILURE"
        print(
            canonical(
                {
                    "comparisons_passed": False,
                    "error_code": code,
                    "error_sha256": sha(message.encode(errors="replace")),
                    "new_model_calls": 0,
                }
            ).decode()
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
