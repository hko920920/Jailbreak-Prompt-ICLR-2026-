from __future__ import annotations

import pytest

from jbspan.programmatic_agentharm.development import (
    decide_development_sweep,
    validate_development_overlay,
)


def gate0_manifest() -> dict[str, object]:
    return {
        "status": "PROGRAMMATIC_AGENTHARM_GATE0_PASS",
        "manifest_identity_sha256": "gate0",
        "target_model_outputs_observed": False,
        "split_assignments": [
            {
                "original_id": "a",
                "category": "Fraud",
                "grading_function": "grade_a",
                "split": "confirmatory",
            },
            {
                "original_id": "b",
                "category": "Hate",
                "grading_function": "grade_b",
                "split": "confirmatory",
            },
            {
                "original_id": "c",
                "category": "Drugs",
                "grading_function": "grade_c",
                "split": "confirmatory",
            },
            {
                "original_id": "d",
                "category": "Copyright",
                "grading_function": "grade_d",
                "split": "confirmatory",
            },
            {
                "original_id": "e",
                "category": "Cybercrime",
                "grading_function": "grade_e",
                "split": "final",
            },
        ],
    }


def runtime_config() -> dict[str, object]:
    return {
        "gate0": {
            "manifest_path": "gate0.json",
            "required_status": "PROGRAMMATIC_AGENTHARM_GATE0_PASS",
            "manifest_identity_sha256": "gate0",
        },
        "attack_programs": {
            "selected_candidate_ids": ["attack_a", "attack_b"],
        },
    }


def overlay() -> dict[str, object]:
    return {
        "schema_version": "programmatic-agentharm-development-expansion-v1",
        "frozen": True,
        "paper_validity": False,
        "gate0": {
            "manifest_path": "gate0.json",
            "required_status": "PROGRAMMATIC_AGENTHARM_GATE0_PASS",
            "manifest_identity_sha256": "gate0",
        },
        "source_split_consumed": "confirmatory",
        "selected_candidate_ids": ["attack_a", "attack_b"],
        "development_behaviors": [
            {
                "original_id": "a",
                "category": "Fraud",
                "grading_function": "grade_a",
            },
            {
                "original_id": "b",
                "category": "Hate",
                "grading_function": "grade_b",
            },
            {
                "original_id": "c",
                "category": "Drugs",
                "grading_function": "grade_c",
            },
            {
                "original_id": "d",
                "category": "Copyright",
                "grading_function": "grade_d",
            },
        ],
        "minimums": {
            "expected_behavior_count": 4,
        },
        "future_use_policy": {
            "consumed_rows_are_development_only": True,
            "consumed_rows_may_enter_paper_confirmatory": False,
            "final_split_untouched": True,
            "heldout_split_untouched": True,
        },
        "claim_boundary": {
            "eligible_pair_signal_is_paper_valid": False,
            "candidate_reselection_allowed": False,
            "case_specific_prompt_rewriting_allowed": False,
            "paper_confirmatory_outputs_observed": False,
            "final_outputs_observed": False,
            "heldout_outputs_observed": False,
            "causal_oracle_allowed": False,
            "wavelet_allowed": False,
        },
    }


def test_development_overlay_consumes_only_confirmatory_rows() -> None:
    assignments = validate_development_overlay(
        overlay(),
        gate0_manifest=gate0_manifest(),
        runtime_config=runtime_config(),
    )
    assert [item.original_id for item in assignments] == ["a", "b", "c", "d"]


def test_development_overlay_rejects_final_row() -> None:
    value = overlay()
    behaviors = value["development_behaviors"]
    assert isinstance(behaviors, list)
    behaviors[-1] = {
        "original_id": "e",
        "category": "Cybercrime",
        "grading_function": "grade_e",
    }
    with pytest.raises(ValueError, match="not from confirmatory"):
        validate_development_overlay(
            value,
            gate0_manifest=gate0_manifest(),
            runtime_config=runtime_config(),
        )


def record(
    behavior_id: str,
    candidate_id: str | None,
    *,
    success: bool,
) -> dict[str, object]:
    return {
        "behavior_id": behavior_id,
        "candidate_id": candidate_id,
        "completed": True,
        "programmatic_score_parsed": True,
        "programmatic_success": success,
    }


def test_development_decision_finds_eligible_pair() -> None:
    records = [
        record("a-1", None, success=False),
        record("a-1", "attack_a", success=False),
        record("a-1", "attack_b", success=True),
        record("b-1", None, success=False),
        record("b-1", "attack_a", success=False),
        record("b-1", "attack_b", success=False),
    ]
    decision = decide_development_sweep(
        records,
        behavior_ids=("a-1", "b-1"),
        candidate_ids=("attack_a", "attack_b"),
        minimum_coverage=1.0,
    )
    assert decision.operational_pass is True
    assert decision.scientific_signal == "ELIGIBLE_PAIRS_FOUND"
    assert decision.eligible_pairs == (("a-1", "attack_b"),)


def test_development_decision_distinguishes_direct_success() -> None:
    records = [
        record("a-1", None, success=True),
        record("a-1", "attack_a", success=True),
        record("a-1", "attack_b", success=True),
    ]
    decision = decide_development_sweep(
        records,
        behavior_ids=("a-1",),
        candidate_ids=("attack_a", "attack_b"),
        minimum_coverage=1.0,
    )
    assert decision.eligible_pairs == ()
    assert decision.direct_success_behavior_ids == ("a-1",)
    assert decision.scientific_signal == "NO_ELIGIBLE_PAIRS_SOME_DIRECT_SUCCESS"


def test_development_decision_fails_on_missing_episode() -> None:
    records = [
        record("a-1", None, success=False),
        record("a-1", "attack_a", success=False),
    ]
    decision = decide_development_sweep(
        records,
        behavior_ids=("a-1",),
        candidate_ids=("attack_a", "attack_b"),
        minimum_coverage=1.0,
    )
    assert decision.operational_pass is False
    assert "EPISODE_KEYSET_MISMATCH" in decision.failures
