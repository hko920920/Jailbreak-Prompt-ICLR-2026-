"""Predeclared safe-only V4 joint-event analysis; never dispatches a model call.

The primary result is a fixed-panel identification interval, not a confidence
interval. Paired resampling is explicitly approximate generator sensitivity.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jbspan import rescue_guidedeval_development as support  # noqa: E402

SCHEMA = "jbspan-objective-transfer-analysis-v4"
STATUSES = ("CORRECT", "INCORRECT", "UNKNOWN")
BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 2026090511
SAFE_FIELDS = {
    "status",
    "error_code",
    "score_reason",
    "reply_sha256",
    "output_sha256",
    "finish_reason_sha256",
    "returned_model_sha256",
    "completion_tokens",
    "elapsed_seconds",
    "private_receipt_sha256",
}


def runner_module():
    path = Path(__file__).with_name("run_rescue_objective_transfer_v4.py")
    spec = importlib.util.spec_from_file_location("_objective_transfer_analysis_runner_v4", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot import V4 read-only verification helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status_counts(values):
    tally = Counter(values)
    return {status: tally[status] for status in STATUSES}


def verify_safe_result(value, contract_sha, plan):
    runner = runner_module()
    runner.verify_result(value, contract_sha, plan)
    rows = value["rows"]
    if (
        value.get("logical_rows") != 1280
        or value.get("unique_phase_requests") != 1120
        or value.get("total_journaled_unique_requests") != 1120
        or value.get("completed_unique_replies") != 1120
        or value.get("fixed_frame_counts") != runner.frame_counts(plan)
        or value.get("stratum_views") != runner.stratum_views(rows)
        or value.get("counts") != status_counts(row["status"] for row in rows)
        or value.get("no_outcome_selection") is not True
        or value.get("no_v3_response_reuse") is not True
    ):
        raise ValueError("fixed frame, provenance, or logical denominator differs")
    executions = {}
    for row, planned in zip(rows, plan, strict=True):
        public = runner.public_plan([planned])[0]
        if set(row) != set(public) | SAFE_FIELDS:
            raise ValueError("safe row fields differ from frozen transport schema")
        status = row["status"]
        if status == "UNKNOWN":
            if not isinstance(row["error_code"], str) or not row["error_code"]:
                raise ValueError("unknown result requires an operational error")
            if row["score_reason"] is not None:
                raise ValueError("unknown result cannot carry a completed score")
        else:
            allowed = (
                {"EXACT_JSON_OBJECT"}
                if status == "CORRECT"
                else {"MALFORMED_JSON", "WRONG_SCHEMA", "WRONG_VALUE", "COMPLETED_REFUSAL"}
            )
            if row["error_code"] is not None or row["score_reason"] not in allowed:
                raise ValueError("completed objective label/reason differs")
            if row["returned_model_sha256"] != support.digest(planned["request"]["model"]) or row[
                "finish_reason_sha256"
            ] != support.digest("stop"):
                raise ValueError("completed result does not bind target alias and stop reason")
        for key in SAFE_FIELDS:
            if key.endswith("sha256"):
                digest = row[key]
                if digest is None and status == "UNKNOWN" and key != "private_receipt_sha256":
                    continue
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)
                ):
                    raise ValueError("malformed safe provenance digest")
        elapsed = row["elapsed_seconds"]
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("invalid elapsed time")
        tokens = row["completion_tokens"]
        if tokens is not None and (type(tokens) is not int or tokens < 0):
            raise ValueError("invalid completion token count")
        safe = {key: row[key] for key in SAFE_FIELDS}
        if executions.setdefault(row["execution_key"], safe) != safe:
            raise ValueError("shared execution has contradictory safe outcomes")
    if len(executions) != 1120 or value.get("unique_request_counts") != dict(
        Counter(row["status"] for row in executions.values())
    ):
        raise ValueError("unique execution denominator differs")
    return rows


def joint_bounds(literals):
    """Three-valued conjunction: one known false dominates any unknowns."""
    literals = list(literals)
    if any(actual not in STATUSES or desired not in STATUSES[:2] for actual, desired in literals):
        raise ValueError("invalid observed status or literal target")
    if any(actual != "UNKNOWN" and actual != desired for actual, desired in literals):
        return {"lower": 0, "upper": 0, "state": "KNOWN_FALSE"}
    if any(actual == "UNKNOWN" for actual, _desired in literals):
        return {"lower": 0, "upper": 1, "state": "UNRESOLVED"}
    return {"lower": 1, "upper": 1, "state": "KNOWN_TRUE"}


def summarize_bounds(values):
    values = list(values)
    if not values:
        raise ValueError("empty event denominator")
    lower = sum(value["lower"] for value in values)
    upper = sum(value["upper"] for value in values)
    return {
        "denominator": len(values),
        "known_true_count": lower,
        "possible_true_count": upper,
        "known_false_count": len(values) - upper,
        "unresolved_count": upper - lower,
        "fixed_panel_rate_bounds": [lower / len(values), upper / len(values)],
        "interval_type": "FIXED_PANEL_IDENTIFICATION_BOUNDS_NOT_CONFIDENCE_INTERVAL",
    }


def paired_correctness_bounds(source_status, target_status):
    source = joint_bounds([(source_status, "CORRECT")])
    target = joint_bounds([(target_status, "CORRECT")])
    return {"lower": source["lower"] - target["upper"], "upper": source["upper"] - target["lower"]}


def case_view(case, stratum, rows):
    witness = stratum["witness_mask"]
    expected = {
        ("SOURCE_PROPER", mask) for mask in range(32) if mask != witness and mask & witness == mask
    }
    expected |= {
        ("SOURCE_WITNESS", witness),
        ("TARGET_WITNESS", witness),
        ("CLEAN", 31),
        ("ALL_BLANK", 31),
        ("ALIGNED", 0),
    }
    cells = {(row["query_role"], row["removed_mask"]): row for row in rows}
    if len(cells) != len(rows) or set(cells) != expected:
        raise ValueError("missing, duplicate, or unexpected within-case query roles")
    if any(row["status"] not in STATUSES for row in rows):
        raise ValueError("unknown objective label")
    source = cells[("SOURCE_WITNESS", witness)]
    target = cells[("TARGET_WITNESS", witness)]
    proper = [cells[key] for key in sorted(cells) if key[0] == "SOURCE_PROPER"]
    controls = [
        cells[(role, mask)] for role, mask in (("CLEAN", 31), ("ALL_BLANK", 31), ("ALIGNED", 0))
    ]
    certificate_literals = [(source["status"], "CORRECT")] + [
        (row["status"], "INCORRECT") for row in proper
    ]
    control_literals = [(row["status"], "CORRECT") for row in controls]
    failure_literals = certificate_literals + control_literals + [(target["status"], "INCORRECT")]
    preservation_literals = certificate_literals + [(target["status"], "CORRECT")]
    # Shared execution requirements must agree before pooled marginal upper bounds
    # can be described as jointly attainable. Current primary masks are incomparable.
    requirements = [(source["execution_key"], "CORRECT"), (target["execution_key"], "INCORRECT")]
    requirements += [(row["execution_key"], "INCORRECT") for row in proper]
    requirements += [(row["execution_key"], "CORRECT") for row in controls]
    return {
        "stratum_id": stratum["stratum_id"],
        "stratum_role": stratum["role"],
        "model_id": stratum["model_id"],
        "case_id": case["case_id"],
        "task_data_id": case["task_data_id"],
        "task_family": case["task_family"],
        "conflict_style": case["conflict_style"],
        "witness_mask": witness,
        "lookup_key_position": int(case["task_data"].split("K")[1])
        if case["task_family"] == "lookup"
        else None,
        "source_certificate": joint_bounds(certificate_literals),
        "controls_correct": joint_bounds(control_literals),
        "primary_joint_transfer_failure": joint_bounds(failure_literals),
        "source_certificate_and_target_correct": joint_bounds(preservation_literals),
        "controls_qualified_preservation": joint_bounds(preservation_literals + control_literals),
        "paired_source_minus_target_correctness": paired_correctness_bounds(
            source["status"], target["status"]
        ),
        "source_status": source["status"],
        "target_status": target["status"],
        "control_statuses": {row["query_role"]: row["status"] for row in controls},
        "known_incorrect_control_count": sum(row["status"] == "INCORRECT" for row in controls),
        "unknown_control_count": sum(row["status"] == "UNKNOWN" for row in controls),
        "unknown_query_count": sum(row["status"] == "UNKNOWN" for row in rows),
        "proper_subset_count": len(proper),
        "includes_empty_proper_subset": ("SOURCE_PROPER", 0) in cells,
        "primary_literal_requirements": requirements,
    }


def primary_panel(views):
    primary = [row for row in views if row["stratum_role"] == "PRIMARY"]
    if len(primary) != 128 or len({row["stratum_id"] for row in primary}) != 4:
        raise ValueError("four complete 32-case primary strata are required")
    by_cluster = defaultdict(list)
    requirements = {}
    for row in primary:
        by_cluster[row["task_data_id"]].append(row)
        for execution_key, desired in row["primary_literal_requirements"]:
            if requirements.setdefault(execution_key, desired) != desired:
                raise ValueError("shared primary events have incompatible latent requirements")
    if len(by_cluster) != 64 or any(len(rows) != 2 for rows in by_cluster.values()):
        raise ValueError("64 paired task clusters, each with two primary views, are required")
    result = summarize_bounds(row["primary_joint_transfer_failure"] for row in primary)
    result.update(
        {
            "weighting": "EQUAL_FOUR_STRATA_EQUIVALENT_TO_MEAN_OF_64_PAIRED_CLUSTER_MEANS",
            "independent_observation_claim": False,
            "task_cluster_count": 64,
            "primary_stratum_count": 4,
            "comparison_included": False,
            "joint_upper_bound_requirements_compatible": True,
            "known_witness_task_cluster_count": sum(
                any(row["primary_joint_transfer_failure"]["lower"] for row in rows)
                for rows in by_cluster.values()
            ),
        }
    )
    return result


def quantile(values, probability):
    ordered = sorted(values)
    location = (len(ordered) - 1) * probability
    left = int(location)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (location - left) * (ordered[right] - ordered[left])


def known_constant(values):
    values = list(values)
    return (
        bool(values)
        and all(value["lower"] == value["upper"] for value in values)
        and len({value["lower"] for value in values}) == 1
    )


def bootstrap_sensitivity(views, *, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """Whole-task paired resampling; no nominal confidence-coverage claim."""
    if type(draws) is not int or draws < 1:
        raise ValueError("positive integer bootstrap draw count required")
    primary_panel(views)
    indexed = {}
    buckets = defaultdict(set)
    for row in views:
        key = (row["stratum_id"], row["task_data_id"])
        if key in indexed:
            raise ValueError("duplicate stratum task-cluster view")
        indexed[key] = row
        buckets[(row["task_family"], row["lookup_key_position"])].add(row["task_data_id"])
    expected_buckets = {("lookup", position): 8 for position in range(1, 5)} | {("sort", None): 32}
    if {key: len(value) for key, value in buckets.items()} != expected_buckets:
        raise ValueError("bootstrap must preserve four balanced key positions and 32 sort clusters")
    strata = sorted({row["stratum_id"] for row in views})
    if len(strata) != 5:
        raise ValueError("all five paired stratum views required")
    per_stratum = {key: [row for row in views if row["stratum_id"] == key] for key in strata}
    if any(len(rows) != 32 for rows in per_stratum.values()):
        raise ValueError("all bootstrap stratum denominators must remain 32")
    event_fields = {
        key: (
            "primary_joint_transfer_failure"
            if rows[0]["stratum_role"] == "PRIMARY"
            else "source_certificate_and_target_correct"
        )
        for key, rows in per_stratum.items()
    }
    primary_ids = [key for key in strata if per_stratum[key][0]["stratum_role"] == "PRIMARY"]
    constant = {
        key: known_constant(row[event_fields[key]] for row in per_stratum[key]) for key in strata
    }
    primary_constant = known_constant(
        row["primary_joint_transfer_failure"] for row in views if row["stratum_role"] == "PRIMARY"
    )
    primary_constant_strata = all(constant[key] for key in primary_ids)
    result = {
        "label": "APPROXIMATE_GENERATOR_SENSITIVITY",
        "not_confidence_interval": True,
        "population_coverage_claim": False,
        "draws": draws,
        "seed": seed,
        "resampling": "PAIRED_TASK_CLUSTERS_LOOKUP_WITHIN_KEY_POSITION_AND_SORT_WITHIN_FAMILY",
        "same_indices_for_lower_upper_and_all_models_masks": True,
        "limitations": [
            "BALANCED_AND_WITHOUT_REPLACEMENT_GENERATOR",
            "FIXED_TEMPLATE_AND_MODEL_SCOPE",
            "NO_STOCHASTIC_SEED_REPLICATION",
        ],
    }
    samples = {key: ([], []) for key in strata}
    pooled = ([], [])
    rng = random.Random(seed)
    executed = 0 if all(constant.values()) else draws
    for _ in range(executed):
        selected = {
            key: rng.choices(sorted(values), k=len(values))
            for key, values in sorted(buckets.items())
        }
        means = {}
        for stratum in strata:
            family = per_stratum[stratum][0]["task_family"]
            ids = [
                task_id
                for (task_family, _position), task_ids in selected.items()
                if task_family == family
                for task_id in task_ids
            ]
            events = [indexed[(stratum, task_id)][event_fields[stratum]] for task_id in ids]
            means[stratum] = (
                sum(value["lower"] for value in events) / 32,
                sum(value["upper"] for value in events) / 32,
            )
            for side in (0, 1):
                samples[stratum][side].append(means[stratum][side])
        for side in (0, 1):
            pooled[side].append(sum(means[key][side] for key in primary_ids) / 4)

    def interval(series, unavailable):
        return None if unavailable else [quantile(series[0], 0.025), quantile(series[1], 0.975)]

    result.update(
        {
            "executed_draws": executed,
            "primary_interval": interval(pooled, primary_constant or primary_constant_strata),
            "primary_interval_status": "UNAVAILABLE_KNOWN_CONSTANT_PANEL"
            if primary_constant
            else "UNAVAILABLE_KNOWN_CONSTANT_STRATA"
            if primary_constant_strata
            else "APPROXIMATE_ONLY",
            "strata": {
                key: {
                    "event": event_fields[key],
                    "interval": interval(samples[key], constant[key]),
                    "status": "UNAVAILABLE_KNOWN_CONSTANT_STRATUM"
                    if constant[key]
                    else "APPROXIMATE_ONLY",
                }
                for key in strata
            },
        }
    )
    return result


def analyze_rows(cases, strata, rows, *, bootstrap_draws=BOOTSTRAP_DRAWS):
    by_case = {case["case_id"]: case for case in cases}
    by_stratum = {stratum["stratum_id"]: stratum for stratum in strata}
    groups = defaultdict(list)
    for row in rows:
        groups[(row["stratum_id"], row["case_id"])].append(row)
    expected = {
        (stratum["stratum_id"], case["case_id"])
        for stratum in strata
        for case in cases
        if case["task_family"] == stratum["task_family"]
        and case["conflict_style"] == stratum["conflict_style"]
    }
    if set(groups) != expected:
        raise ValueError("fixed no-selection stratum-case frame differs")
    views = [
        case_view(by_case[case_id], by_stratum[stratum_id], group)
        for (stratum_id, case_id), group in sorted(groups.items())
    ]
    summaries = []
    for stratum_id, stratum in sorted(by_stratum.items()):
        selected = [row for row in views if row["stratum_id"] == stratum_id]
        if len(selected) != 32 or len({row["task_data_id"] for row in selected}) != 32:
            raise ValueError("every stratum must contain all 32 unique tasks")
        event_keys = (
            "primary_joint_transfer_failure",
            "source_certificate",
            "controls_correct",
            "source_certificate_and_target_correct",
            "controls_qualified_preservation",
        )
        summaries.append(
            {
                **stratum,
                "denominator": 32,
                **{key: summarize_bounds(row[key] for row in selected) for key in event_keys},
                "paired_source_minus_target_correctness_bounds": [
                    sum(row["paired_source_minus_target_correctness"][side] for row in selected)
                    / 32
                    for side in ("lower", "upper")
                ],
                "cases_with_known_control_failure": sum(
                    row["known_incorrect_control_count"] > 0 for row in selected
                ),
                "cases_with_unknown_control": sum(
                    row["unknown_control_count"] > 0 for row in selected
                ),
                "individual_control_status_counts": {
                    role: status_counts(row["control_statuses"][role] for row in selected)
                    for role in ("CLEAN", "ALL_BLANK", "ALIGNED")
                },
                "source_status_counts": status_counts(row["source_status"] for row in selected),
                "target_status_counts": status_counts(row["target_status"] for row in selected),
            }
        )
    primary = primary_panel(views)
    sensitivity = bootstrap_sensitivity(views, draws=bootstrap_draws)
    public_views = [
        {key: value for key, value in row.items() if key != "primary_literal_requirements"}
        for row in views
    ]
    result = {
        "logical_row_count": len(rows),
        "stratum_task_opportunity_count": len(views),
        "task_cluster_count": len({row["task_data_id"] for row in views}),
        "primary": primary,
        "strata": summaries,
        "case_views": public_views,
        "bootstrap_sensitivity": sensitivity,
        "all_denominators_unconditional": True,
    }
    support.content_free(result)
    return result


def analyze(root, relative, contract_sha):
    runner = runner_module()
    config, cases, strata, helper = runner.verify_config(root, relative, contract_sha)
    plan = runner.build_plan(config, cases, strata, helper)
    runner.verify_plan(plan, config)
    directory = support.contained(root, config["recording"]["safe_base"]) / contract_sha
    source = directory / "validation.safe.json"
    value = support.read_object(source)
    rows = verify_safe_result(value, contract_sha, plan)
    result = {
        "schema_version": SCHEMA,
        "status": "FIXED_FRAME_SAFE_ANALYSIS_COMPLETE",
        "contract_sha256": contract_sha,
        "validation_file_sha256": support.file_digest(source),
        "analysis_source_sha256": support.file_digest(Path(__file__)),
        "analysis_test_sha256": support.file_digest(
            root / "tests/test_objective_transfer_analysis_v4.py"
        ),
        "analysis": analyze_rows(cases, strata, rows),
        "scope": "FRESH_PROBLEMS_UNDER_FIXED_V3_TEMPLATES_MODELS_AND_DECODING",
        "interpretation": {
            "primary_event": (
                "THREE_CONTROLS_CORRECT_AND_SOURCE_SUBSET_MINIMAL_AND_TARGET_INCORRECT"
            ),
            "comparison_event": "SOURCE_SUBSET_MINIMAL_AND_TARGET_CORRECT",
            "source_minimality_is_not_minimum_cardinality": True,
            "not_full_five_unit_minimal_family_enumeration": True,
            "not_new_model_or_task_family_generalization": True,
            "not_safety_validation": True,
            "p_value": None,
            "paper_quality_gate": None,
            "outcome_dependent_exclusion_or_stopping": False,
        },
        "network_calls": 0,
        "private_inputs_read": False,
        "model_files_read": False,
    }
    support.content_free(result)
    result["result_identity_sha256"] = support.digest(result)
    return result, directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result, directory = analyze(args.root.resolve(), args.config, args.config_sha256)
    if args.write:
        support.write_once(directory / "analysis.safe.json", result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
