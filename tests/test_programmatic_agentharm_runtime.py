from __future__ import annotations

import pytest

from jbspan.programmatic_agentharm.runtime import (
    canonical_validation_record,
    decide_operational_smoke,
    strict_boolean_criteria,
    trace_hash,
)


def validation_payload() -> dict[str, object]:
    return {
        "behaviors": [
            {
                "id": "a-0",
                "id_original": "a",
                "category": "Fraud",
                "grading_function": "grade_programmatic",
                "detailed_prompt": False,
                "hint_included": False,
            },
            {
                "id": "a-1",
                "id_original": "a",
                "category": "Fraud",
                "grading_function": "grade_programmatic",
                "detailed_prompt": True,
                "hint_included": True,
            },
            {
                "id": "b-1",
                "id_original": "b",
                "category": "Other",
                "grading_function": "grade_semantic",
                "detailed_prompt": True,
                "hint_included": True,
            },
        ]
    }


def test_canonical_validation_record_prefers_requested_variant() -> None:
    record = canonical_validation_record(
        validation_payload(),
        eligible_graders={"grade_programmatic"},
        detailed_prompt=True,
        hint_included=True,
        fallback_seed="fixed",
    )
    assert record.behavior_id == "a-1"


def test_strict_boolean_criteria_rejects_numeric_partial_credit() -> None:
    assert strict_boolean_criteria({"called": True, "ordered": False}) == {
        "called": True,
        "ordered": False,
    }
    with pytest.raises(ValueError, match="strict booleans"):
        strict_boolean_criteria({"partial": 0.5})


def test_trace_hash_is_canonical() -> None:
    assert trace_hash({"b": 2, "a": 1}) == trace_hash({"a": 1, "b": 2})


def test_operational_smoke_pass_does_not_require_attack_success() -> None:
    records = [
        {
            "condition": "forced_first_probe",
            "completed": True,
            "programmatic_score_parsed": True,
            "programmatic_success": False,
            "tool_call_count": 1,
        },
        {
            "condition": "original_auto",
            "completed": True,
            "programmatic_score_parsed": True,
            "programmatic_success": False,
            "tool_call_count": 0,
        },
        {
            "condition": "attacked_auto",
            "completed": True,
            "programmatic_score_parsed": True,
            "programmatic_success": False,
            "tool_call_count": 0,
        },
    ]
    decision = decide_operational_smoke(
        records,
        expected_episodes=3,
        minimum_coverage=1.0,
        forced_first_minimum_tool_calls=1,
    )
    assert decision.operational_pass is True
    assert decision.attacked_success is False


def test_operational_smoke_fails_without_forced_tool_call() -> None:
    records = [
        {
            "condition": condition,
            "completed": True,
            "programmatic_score_parsed": True,
            "programmatic_success": False,
            "tool_call_count": 0,
        }
        for condition in ("forced_first_probe", "original_auto", "attacked_auto")
    ]
    decision = decide_operational_smoke(
        records,
        expected_episodes=3,
        minimum_coverage=1.0,
        forced_first_minimum_tool_calls=1,
    )
    assert decision.operational_pass is False
    assert "FORCED_FIRST_TOOL_PATH_FAIL" in decision.failures
