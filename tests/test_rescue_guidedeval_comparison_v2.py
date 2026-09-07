import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/analyze_rescue_guidedeval_development_v2.py"
SPEC = importlib.util.spec_from_file_location("development_comparison", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_pair_conjunction_is_disproved_by_one_known_failure():
    assert MODULE.pair_predicate(MODULE.PRESENT, MODULE.UNKNOWN) == "FALSE"
    assert MODULE.pair_predicate(MODULE.UNKNOWN, MODULE.ZERO) == "FALSE"
    assert MODULE.pair_predicate(MODULE.ZERO, MODULE.PRESENT) == "TRUE_SINGLE_SEED_ONLY"
    assert MODULE.pair_predicate(MODULE.ZERO, MODULE.UNKNOWN) == "UNRESOLVED"


def test_cross_tabs_do_not_treat_new_measurement_as_ground_truth():
    plan, old, new = [], [], []
    for index, condition in enumerate(("DIRECT", "ATTACKED_H4RM3L")):
        row = {
            "plan_row_identity_sha256": str(index),
            "record_id": str(index),
            "payload_sha256": "case",
            "target_id": "target",
            "condition": condition,
            "guideline_count": 2,
        }
        plan.append(row)
        old.append(
            {
                **row,
                "panel_label": "ABSTAIN",
                "qwen_axis_label": "HARMFUL",
                "jailmeter_axis_label": "SAFE",
            }
        )
        new.append(
            {
                "identity": {"judge_id": "judge", "plan_row_identity_sha256": str(index)},
                "outcome": MODULE.ZERO if index == 0 else MODULE.PRESENT,
                "error_code": None,
                "points": [
                    {"guideline_type": "entity", "matched": index == 1},
                    {"guideline_type": "action", "matched": False},
                ],
            }
        )
    result = MODULE.compare(plan, old, new)
    assert result["pair_predicates"]["judge|target"] == {"TRUE_SINGLE_SEED_ONLY": 1}
    assert result["cells"]["judge|target|ATTACKED_H4RM3L"]["present_from_entities_only"] == 1
    assert result["c1n_reclassified"] is False
    with pytest.raises(ValueError, match="complete frozen"):
        MODULE.compare(plan, old, new[:1])
