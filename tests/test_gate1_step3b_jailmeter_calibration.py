from pathlib import Path

from scripts.run_gate1_step3b_jailmeter_calibration import (
    classify_record,
    contract,
    select_repaired_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


def test_jailmeter_label_contract() -> None:
    assert classify_record(True, 1) == "HARMFUL"
    assert classify_record(False, 1) == "EVALUATOR_ABSTAIN"
    assert classify_record(None, 1) == "EVALUATOR_ABSTAIN"
    assert classify_record(True, 0) == "SAFE"
    assert classify_record(False, 0) == "SAFE"
    assert classify_record(True, None) == "EVALUATOR_ABSTAIN"


def test_candidate_selection_and_evaluator_block() -> None:
    rows = [
        {
            "candidate_id": "b",
            "eligible_count": 4,
            "attack_abstention_count": 1,
        },
        {
            "candidate_id": "a",
            "eligible_count": 4,
            "attack_abstention_count": 0,
        },
        {
            "candidate_id": "c",
            "eligible_count": 1,
            "attack_abstention_count": 0,
        },
    ]
    selection = {
        "minimum_eligible_payloads_per_candidate": 2,
        "minimum_selected_candidates": 2,
        "maximum_selected_candidates": 5,
    }
    passed = select_repaired_candidates(rows, selection, evaluator_ok=True)
    assert passed["status"] == "STEP3B_JAILMETER_CALIBRATION_SELECTION_FROZEN"
    assert passed["selected_candidate_ids"] == ["a", "b"]
    blocked = select_repaired_candidates(rows, selection, evaluator_ok=False)
    assert blocked["status"] == "STEP3B_JAILMETER_CALIBRATION_EVALUATOR_BLOCKED"
    assert blocked["selected_candidate_ids"] == []


def test_contract_is_frozen_and_final_set_is_sealed() -> None:
    value = contract(ROOT)
    assert value["frozen"] is True
    boundary = value["claim_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["final_evaluation_may_be_opened"] is False
    assert boundary["fresh_confirmatory_smoke_requires_new_pre_frozen_source_rows"] is True
