"""Synthetic-only checks: no model calls or completed pilot outcomes are read."""

import copy
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/analyze_rescue_objective_repair_v3.py"
SPEC = importlib.util.spec_from_file_location("objective_analysis_v3_test", PATH)
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


def table(positive=(), unknown=()):
    return {
        mask: "UNKNOWN" if mask in unknown else "CORRECT" if mask in positive else "INCORRECT"
        for mask in range(32)
    }


def fixture_bundle():
    runner = ANALYSIS.runner_module()
    cases = runner.core_module().build_cases()
    config = {
        "models": [{"model_id": "m1", "alias": "one"}, {"model_id": "m2", "alias": "two"}],
        "decoding": {"temperature": 0, "seed": 11},
    }
    plan = runner.screen_plan(config, cases)
    rows = []
    for planned in runner.public_plan(plan):
        status = "INCORRECT" if planned["condition"] == "UNEDITED" else "CORRECT"
        rows.append(
            {
                **planned,
                "status": status,
                "error_code": None,
                "score_reason": "WRONG_VALUE" if status == "INCORRECT" else "EXACT_JSON_OBJECT",
                "reply_sha256": "a" * 64,
                "output_sha256": "b" * 64,
                "finish_reason_sha256": "c" * 64,
                "returned_model_sha256": "d" * 64,
                "private_receipt_sha256": "e" * 64,
                "completion_tokens": 8,
                "elapsed_seconds": 1.0,
            }
        )
    result = {"rows": rows}
    selected = runner.select_eligible(config, cases, result)
    total = len({row["execution_key"] for row in plan})
    result.update(
        {
            "schema_version": runner.SCHEMA,
            "phase": "screen",
            "contract_sha256": "f" * 64,
            "complete": True,
            "plan_sha256": ANALYSIS.support.digest(runner.public_plan(plan)),
            "logical_rows": len(rows),
            "unique_phase_requests": total,
            "total_journaled_unique_requests": total,
            "selected_case_ids": selected,
            "screen_file_sha256": None,
            "counts": ANALYSIS.counts(row["status"] for row in rows),
        }
    )
    result["result_identity_sha256"] = ANALYSIS.support.digest(result)
    return config, cases, plan, selected, total, result


def reseal(value):
    value.pop("result_identity_sha256", None)
    value["result_identity_sha256"] = ANALYSIS.support.digest(value)


def test_known_nonmonotone_one_minimal_is_not_strict_minimal():
    result = ANALYSIS.analyze_table(table(positive={1, 7, 31}))
    assert result["necessary_minimum_masks"] == [1]
    candidate = next(row for row in result["known_one_minimal_candidates"] if row["mask"] == 7)
    assert candidate["strict_status"] == "REFUTED_BY_KNOWN_STRICT_SUBSET"
    assert candidate["known_correct_proper_masks"] == [1]
    assert {"correct_mask": 1, "incorrect_superset_mask": 3} in result[
        "known_nonmonotone_witnesses"
    ]
    assert result["adjacent_known_closure_witness_count"] == 1


def test_unknown_proper_subset_never_becomes_negative_certificate():
    result = ANALYSIS.analyze_table(table(positive={7, 31}, unknown={1}))
    candidate = next(row for row in result["known_one_minimal_candidates"] if row["mask"] == 7)
    assert candidate["strict_status"] == "UNRESOLVED_STRICT_MINIMALITY"
    assert candidate["known_correct_proper_masks"] == []
    assert result["necessary_minimum_masks"] == []
    assert 1 in result["possible_minimum_masks"] and 7 in result["possible_minimum_masks"]
    assert result["family_identified"] is False


def test_monotone_pair_has_exact_family_and_no_reversal():
    result = ANALYSIS.analyze_table(table(positive={mask for mask in range(32) if mask & 3 == 3}))
    assert result["necessary_minimum_masks"] == result["possible_minimum_masks"] == [3]
    assert result["known_nonmonotone_witness_count"] == 0
    for baseline in result["baselines"]:
        assert baseline["final_mask"] == 3
        assert baseline["transcript_certificate"]["strict_status"] == "CERTIFIED_STRICT_MINIMAL"


def test_greedy_does_not_peek_at_unqueried_positive_or_promote_unknown():
    original = table(positive={31}, unknown={30})
    changed = dict(original, **{})
    changed[3] = "CORRECT"
    first = ANALYSIS.greedy_replay(original)
    second = ANALYSIS.greedy_replay(changed)
    assert first["new_queries"] == second["new_queries"]
    assert first["moves"] == second["moves"] == []
    assert first["transcript_certificate"] == second["transcript_certificate"]
    assert first["transcript_certificate"]["known_one_minimal"] is False
    assert second["full_table_posthoc_audit"]["strict_status"] == "REFUTED_BY_KNOWN_STRICT_SUBSET"


def test_unknown_closure_not_counted_as_known_reversal():
    result = ANALYSIS.analyze_table(table(positive={1, 31}, unknown={3}))
    assert result["adjacent_known_closure_witness_count"] == 0
    assert result["adjacent_unresolved_closure_count"] == 1


def test_identity_verifier_accepts_synthetic_bound_phase():
    _config, _cases, plan, selected, total, result = fixture_bundle()
    assert len(ANALYSIS.verify_phase(result, plan, "f" * 64, "screen", selected, None, total)) == 64


@pytest.mark.parametrize(
    "mutation", ["digest", "row", "duplicate", "count", "plan", "selection", "cache"]
)
def test_identity_or_denominator_tampering_fails_even_when_resealed(mutation):
    _config, _cases, plan, selected, total, result = fixture_bundle()
    result = copy.deepcopy(result)
    if mutation == "digest":
        result["result_identity_sha256"] = "0" * 64
    else:
        if mutation == "row":
            result["rows"][0]["removed_mask"] = 0
        elif mutation == "duplicate":
            result["rows"][1] = result["rows"][0]
        elif mutation == "count":
            result["counts"]["CORRECT"] += 1
        elif mutation == "plan":
            result["plan_sha256"] = "0" * 64
        elif mutation == "selection":
            result["selected_case_ids"] = {}
        else:
            result["rows"][0]["output_sha256"] = "0" * 64
        reseal(result)
    with pytest.raises(ValueError):
        ANALYSIS.verify_phase(result, plan, "f" * 64, "screen", selected, None, total)


def test_model_operator_repetitions_do_not_inflate_unique_task_count():
    config, cases, _plan, selected, _total, screen = fixture_bundle()
    summary = ANALYSIS.screen_summary(config, cases, screen["rows"], selected)
    assert summary["model_case_count"] == 16
    assert summary["unique_case_count"] == 8
    assert summary["unique_task_data_count"] == 4
    selected_cases = [case for case in cases if case["case_id"].endswith("__0")]
    rows = [
        {
            "model_id": model,
            "case_id": case["case_id"],
            "operator": operator,
            "removed_mask": mask,
            "status": status,
        }
        for model in ("m1", "m2")
        for case in selected_cases
        for operator in ANALYSIS.runner_module().OPERATORS
        for mask, status in table(positive={1, 31}, unknown={3}).items()
    ]
    result = ANALYSIS.analyze_exact_rows(cases, rows)
    assert result["operator_table_count"] == 16
    assert result["model_case_count"] == 8
    assert result["unique_case_count"] == 4
    assert result["unique_task_data_count"] == 2
    assert result["known_nonmonotone_unique_task_data_count"] == 2


def test_operator_transfer_retains_unknown():
    case = ANALYSIS.runner_module().core_module().build_cases()[0]
    rows = [
        {
            "model_id": "m",
            "case_id": case["case_id"],
            "operator": operator,
            "removed_mask": mask,
            "status": status,
        }
        for operator, values in (
            ("SOURCE_OMIT", table(positive={1, 31})),
            ("LAYOUT_BLANK", table(positive={31}, unknown={1})),
        )
        for mask, status in values.items()
    ]
    result = ANALYSIS.analyze_exact_rows([case], rows)
    source = next(row for row in result["tables"] if row["operator"] == "SOURCE_OMIT")
    assert source["minimum_operator_transfer_counts"] == {
        "CORRECT": 0,
        "INCORRECT": 0,
        "UNKNOWN": 1,
    }


def test_missing_duplicate_and_invalid_cells_rejected():
    with pytest.raises(ValueError):
        ANALYSIS.analyze_table({mask: "CORRECT" for mask in range(31)})
    with pytest.raises(ValueError):
        ANALYSIS.analyze_table({**table(), 0: "ABSTAINED"})
