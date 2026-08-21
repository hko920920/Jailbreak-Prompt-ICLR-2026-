from jbspan.gate1.step3b_calibration import select_calibration_candidates


def test_selection_uses_frozen_ranking_and_cap() -> None:
    rows = [
        {
            "candidate_id": "candidate_b",
            "eligible_count": 4,
            "attack_abstention_count": 1,
        },
        {
            "candidate_id": "candidate_a",
            "eligible_count": 4,
            "attack_abstention_count": 0,
        },
        {
            "candidate_id": "candidate_c",
            "eligible_count": 3,
            "attack_abstention_count": 0,
        },
        {
            "candidate_id": "candidate_d",
            "eligible_count": 2,
            "attack_abstention_count": 0,
        },
        {
            "candidate_id": "candidate_e",
            "eligible_count": 1,
            "attack_abstention_count": 0,
        },
    ]
    result = select_calibration_candidates(
        rows,
        minimum_eligible=2,
        minimum_selected=2,
        maximum_selected=3,
    )
    assert result["status"] == "STEP3B_CALIBRATION_SELECTION_FROZEN"
    assert result["selected_candidate_ids"] == [
        "candidate_a",
        "candidate_b",
        "candidate_c",
    ]


def test_selection_blocks_smoke_when_too_few_candidates_qualify() -> None:
    rows = [
        {
            "candidate_id": "candidate_a",
            "eligible_count": 2,
            "attack_abstention_count": 0,
        },
        {
            "candidate_id": "candidate_b",
            "eligible_count": 1,
            "attack_abstention_count": 0,
        },
    ]
    result = select_calibration_candidates(
        rows,
        minimum_eligible=2,
        minimum_selected=2,
        maximum_selected=5,
    )
    assert result["status"] == (
        "STEP3B_CALIBRATION_INSUFFICIENT_CANDIDATES"
    )
    assert result["selected_candidate_ids"] == []
    assert result["qualifying_candidate_count"] == 1
