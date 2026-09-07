"""All outcomes below are synthetic; no V4 model outputs or private files read."""

import copy
import importlib.util
from collections import Counter
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/analyze_rescue_objective_transfer_v4.py"
SPEC = importlib.util.spec_from_file_location("objective_transfer_analysis_v4_test", PATH)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def fixture_bundle():
    runner = ANALYSIS.runner_module()
    root = PATH.parents[1]
    helper = runner.frozen_runner(root)
    cases, strata = runner.core_module().build_cases(), runner.core_module().build_strata()
    config = {
        "models": [
            {"model_id": runner.core_module().QWEN, "alias": "q"},
            {"model_id": runner.core_module().GEMMA, "alias": "g"},
        ],
        "decoding": {"temperature": 0, "seed": 11},
        "limits": {"max_request_utf8_bytes": 100000},
    }
    plan = runner.build_plan(config, cases, strata, helper)
    runner.verify_plan(plan, config)
    rows = []
    for planned in plan:
        status = (
            "INCORRECT"
            if planned["query_role"] in {"SOURCE_PROPER", "TARGET_WITNESS"}
            else "CORRECT"
        )
        rows.append(
            {
                **runner.public_plan([planned])[0],
                "status": status,
                "error_code": None,
                "score_reason": "WRONG_VALUE" if status == "INCORRECT" else "EXACT_JSON_OBJECT",
                "reply_sha256": "a" * 64,
                "output_sha256": "b" * 64,
                "finish_reason_sha256": ANALYSIS.support.digest("stop"),
                "returned_model_sha256": ANALYSIS.support.digest(planned["request"]["model"]),
                "private_receipt_sha256": "e" * 64,
                "completion_tokens": 9,
                "elapsed_seconds": 1.0,
            }
        )
    value = {
        "schema_version": runner.SCHEMA,
        "phase": runner.PHASE,
        "contract_sha256": "f" * 64,
        "complete": True,
        "plan_sha256": ANALYSIS.support.digest(runner.public_plan(plan)),
        "logical_rows": 1280,
        "unique_phase_requests": 1120,
        "total_journaled_unique_requests": 1120,
        "completed_unique_replies": 1120,
        "fixed_frame_counts": runner.frame_counts(plan),
        "stratum_views": runner.stratum_views(rows),
        "counts": ANALYSIS.status_counts(row["status"] for row in rows),
        "rows": rows,
        "unique_request_counts": dict(
            Counter(row["status"] for row in {row["execution_key"]: row for row in rows}.values())
        ),
        "no_outcome_selection": True,
        "no_v3_response_reuse": True,
    }
    value["result_identity_sha256"] = ANALYSIS.support.digest(value)
    return cases, strata, plan, rows, value


def reseal(value):
    value.pop("result_identity_sha256", None)
    value["result_identity_sha256"] = ANALYSIS.support.digest(value)


def views_from(cases, strata, rows):
    return [
        ANALYSIS.case_view(
            case,
            stratum,
            [
                row
                for row in rows
                if row["case_id"] == case["case_id"] and row["stratum_id"] == stratum["stratum_id"]
            ],
        )
        for stratum in strata
        for case in cases
        if case["task_family"] == stratum["task_family"]
        and case["conflict_style"] == stratum["conflict_style"]
    ]


def test_false_literal_overrides_unknown_and_true_needs_all_observed():
    assert ANALYSIS.joint_bounds([("UNKNOWN", "CORRECT"), ("CORRECT", "INCORRECT")]) == {
        "lower": 0,
        "upper": 0,
        "state": "KNOWN_FALSE",
    }
    assert ANALYSIS.joint_bounds([("UNKNOWN", "INCORRECT"), ("CORRECT", "CORRECT")]) == {
        "lower": 0,
        "upper": 1,
        "state": "UNRESOLVED",
    }
    assert ANALYSIS.joint_bounds([("INCORRECT", "INCORRECT"), ("CORRECT", "CORRECT")])["lower"] == 1


def test_case_joint_event_includes_all_proper_subsets_and_three_controls():
    cases, strata, _plan, rows, _value = fixture_bundle()
    case = next(case for case in cases if case["case_id"] == rows[0]["case_id"])
    stratum = next(stratum for stratum in strata if stratum["stratum_id"] == rows[0]["stratum_id"])
    group = [
        row
        for row in rows
        if row["case_id"] == case["case_id"] and row["stratum_id"] == stratum["stratum_id"]
    ]
    view = ANALYSIS.case_view(case, stratum, group)
    assert view["primary_joint_transfer_failure"]["lower"] == 1
    assert view["proper_subset_count"] == 2 ** stratum["witness_mask"].bit_count() - 1
    assert view["includes_empty_proper_subset"]
    changed = copy.deepcopy(group)
    next(row for row in changed if row["query_role"] == "TARGET_WITNESS")["status"] = "UNKNOWN"
    assert (
        ANALYSIS.case_view(case, stratum, changed)["primary_joint_transfer_failure"]["state"]
        == "UNRESOLVED"
    )
    next(
        row for row in changed if row["query_role"] == "SOURCE_PROPER" and row["removed_mask"] == 0
    )["status"] = "CORRECT"
    assert (
        ANALYSIS.case_view(case, stratum, changed)["primary_joint_transfer_failure"]["state"]
        == "KNOWN_FALSE"
    )


def test_shared_cluster_weight_and_comparison_exclusion():
    cases, strata, _plan, rows, _value = fixture_bundle()
    views = views_from(cases, strata, rows)
    primary = ANALYSIS.primary_panel(views)
    assert primary["denominator"] == 128 and primary["task_cluster_count"] == 64
    assert primary["known_true_count"] == 128 and primary["known_witness_task_cluster_count"] == 64
    for row in views:
        if row["stratum_role"] == "PRESERVATION_COMPARISON":
            row["primary_joint_transfer_failure"] = {"lower": 0, "upper": 0}
    assert ANALYSIS.primary_panel(views) == primary
    task_id = next(row["task_data_id"] for row in views if row["task_family"] == "sort")
    for row in views:
        if row["task_data_id"] == task_id and row["stratum_role"] == "PRIMARY":
            row["primary_joint_transfer_failure"] = {"lower": 0, "upper": 0}
    assert ANALYSIS.primary_panel(views)["fixed_panel_rate_bounds"] == [63 / 64, 63 / 64]


def test_constant_known_panel_has_no_bootstrap_interval():
    cases, strata, _plan, rows, _value = fixture_bundle()
    views = views_from(cases, strata, rows)
    result = ANALYSIS.bootstrap_sensitivity(views)
    assert result["primary_interval"] is None
    assert result["primary_interval_status"] == "UNAVAILABLE_KNOWN_CONSTANT_PANEL"
    assert result["executed_draws"] == 0
    assert result["draws"] == 10000 and result["seed"] == 2026090511
    for row in views:
        row["primary_joint_transfer_failure"] = {"lower": 0, "upper": 0}
    assert ANALYSIS.bootstrap_sensitivity(views)["primary_interval"] is None


def test_paired_resampling_preserves_model_mask_pair_and_seed():
    cases, strata, _plan, rows, _value = fixture_bundle()
    views = views_from(cases, strata, rows)
    ranks = {
        family: {
            task_id: index
            for index, task_id in enumerate(
                sorted({row["task_data_id"] for row in views if row["task_family"] == family})
            )
        }
        for family in ("lookup", "sort")
    }
    for row in views:
        value = ranks[row["task_family"]][row["task_data_id"]] % 2
        row["primary_joint_transfer_failure"] = {"lower": value, "upper": value}
        row["source_certificate_and_target_correct"] = {"lower": value, "upper": value}
    result = ANALYSIS.bootstrap_sensitivity(views, draws=200)
    assert result == ANALYSIS.bootstrap_sensitivity(views, draws=200)
    assert result["label"] == "APPROXIMATE_GENERATOR_SENSITIVITY"
    assert result["not_confidence_interval"]
    assert (
        result["strata"]["qwen_sort_13"]["interval"] == result["strata"]["qwen_sort_24"]["interval"]
    )
    assert (
        result["strata"]["qwen_lookup_18"]["interval"]
        == result["strata"]["gemma_lookup_2"]["interval"]
    )


def test_different_known_constant_strata_do_not_produce_false_zero_width_pool():
    cases, strata, _plan, rows, _value = fixture_bundle()
    views = views_from(cases, strata, rows)
    for row in views:
        value = int(row["task_family"] == "lookup")
        row["primary_joint_transfer_failure"] = {"lower": value, "upper": value}
    result = ANALYSIS.bootstrap_sensitivity(views)
    assert result["executed_draws"] == 0
    assert result["primary_interval"] is None
    assert result["primary_interval_status"] == "UNAVAILABLE_KNOWN_CONSTANT_STRATA"


def test_unknown_upper_and_lower_use_same_resampled_tasks():
    cases, strata, _plan, rows, _value = fixture_bundle()
    views = views_from(cases, strata, rows)
    for index, row in enumerate(views):
        row["primary_joint_transfer_failure"] = {"lower": 0, "upper": index % 2}
    result = ANALYSIS.bootstrap_sensitivity(views, draws=100)
    assert result["primary_interval"][0] == 0
    assert 0 <= result["primary_interval"][1] <= 1


def test_incompatible_shared_primary_literals_rejected():
    cases, strata, _plan, rows, _value = fixture_bundle()
    views = views_from(cases, strata, rows)
    first = next(row for row in views if row["stratum_role"] == "PRIMARY")
    key, desired = first["primary_literal_requirements"][0]
    first["primary_literal_requirements"].append(
        (key, "INCORRECT" if desired == "CORRECT" else "CORRECT")
    )
    with pytest.raises(ValueError, match="incompatible"):
        ANALYSIS.primary_panel(views)


def test_synthetic_full_result_identity_and_denominators_verify():
    _cases, _strata, plan, rows, value = fixture_bundle()
    assert ANALYSIS.verify_safe_result(value, "f" * 64, plan) == rows


@pytest.mark.parametrize(
    "mutation", ["digest", "duplicate", "missing", "count", "cache", "alias", "frame"]
)
def test_tampered_result_denominators_or_identity_rejected(mutation):
    _cases, _strata, plan, _rows, value = fixture_bundle()
    if mutation == "digest":
        value["result_identity_sha256"] = "0" * 64
    else:
        if mutation == "duplicate":
            value["rows"][1] = value["rows"][0]
        elif mutation == "missing":
            value["rows"].pop()
        elif mutation == "count":
            value["completed_unique_replies"] -= 1
        elif mutation == "cache":
            duplicates = Counter(row["execution_key"] for row in value["rows"])
            next(row for row in value["rows"] if duplicates[row["execution_key"]] > 1)[
                "output_sha256"
            ] = "0" * 64
        elif mutation == "alias":
            value["rows"][0]["returned_model_sha256"] = "0" * 64
        else:
            value["fixed_frame_counts"]["task_data_units"] = 160
        reseal(value)
    with pytest.raises(ValueError):
        ANALYSIS.verify_safe_result(value, "f" * 64, plan)


def test_analysis_fixed_denominators_and_secondary_events():
    cases, strata, _plan, rows, _value = fixture_bundle()
    result = ANALYSIS.analyze_rows(cases, strata, rows)
    assert result["logical_row_count"] == 1280
    assert result["stratum_task_opportunity_count"] == 160
    assert result["task_cluster_count"] == 64
    assert result["primary"]["known_true_count"] == 128
    for stratum in result["strata"]:
        assert stratum["source_certificate"]["known_true_count"] == 32
        assert stratum["controls_correct"]["known_true_count"] == 32
        assert stratum["source_certificate_and_target_correct"]["known_false_count"] == 32
        assert stratum["paired_source_minus_target_correctness_bounds"] == [1, 1]


def test_duplicate_or_missing_query_and_removed_case_are_rejected():
    cases, strata, _plan, rows, _value = fixture_bundle()
    for amended in (rows[1:], rows + [rows[0]]):
        with pytest.raises(ValueError):
            ANALYSIS.analyze_rows(cases, strata, amended)
    first = rows[0]
    remaining = [
        row
        for row in rows
        if (row["case_id"], row["stratum_id"]) != (first["case_id"], first["stratum_id"])
    ]
    with pytest.raises(ValueError):
        ANALYSIS.analyze_rows(cases, strata, remaining)


@pytest.mark.parametrize(
    "source,target,expected",
    [
        ("CORRECT", "INCORRECT", {"lower": 1, "upper": 1}),
        ("UNKNOWN", "CORRECT", {"lower": -1, "upper": 0}),
        ("CORRECT", "UNKNOWN", {"lower": 0, "upper": 1}),
        ("UNKNOWN", "UNKNOWN", {"lower": -1, "upper": 1}),
    ],
)
def test_paired_unknown_correctness_bounds(source, target, expected):
    assert ANALYSIS.paired_correctness_bounds(source, target) == expected
