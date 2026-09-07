from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "scripts"
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import preflight_rescue_guidedeval as preflight  # noqa: E402

CONFIG = ROOT / (
    "configs/natural_language_localization/"
    "rescue_guidedeval_development_preflight_v1.json"
)
RESULT = ROOT / (
    "data/natural_language_localization/rescue_guidedeval_development_v1/"
    "preflight.safe.json"
)
PLAN = ROOT / (
    "data/natural_language_localization/rescue_guidedeval_development_v1/"
    "input_plan.safe.jsonl"
)


def test_preflight_binds_all_four_development_cells_without_inference() -> None:
    result, plan = preflight.build(ROOT, CONFIG)
    assert result["status"] == "RESCUE_GUIDEDEVAL_DEVELOPMENT_INPUT_PREFLIGHT_PASS"
    assert result["counts"]["victim_responses"] == 180
    assert set(result["counts"]["target_condition"].values()) == {45}
    assert len(plan) == 180
    assert result["scope"] == {
        "target_inference_performed": False,
        "judge_inference_performed": False,
        "raw_content_read_for_identity_validation_only": True,
        "raw_content_written_to_safe_artifact": False,
        "raw_response_corpus_duplicated": False,
        "c1n_reclassified": False,
        "primary_a_opened": False,
        "replication_reserve_b_opened": False,
        "paper_valid_evidence": False,
    }


def test_safe_plan_contains_only_hash_identity_and_provenance_fields() -> None:
    _result, plan = preflight.build(ROOT, CONFIG)
    preflight.assert_content_free(plan)
    assert len({row["record_id"] for row in plan}) == 180
    assert len({row["payload_sha256"] for row in plan}) == 45
    assert all(row["raw_content_recorded"] is False for row in plan)
    assert all(row["judge_inference_completed"] is False for row in plan)


def test_stored_preflight_and_plan_match_reconstruction() -> None:
    stored_result = json.loads(RESULT.read_text(encoding="utf-8"))
    stored_plan = [
        json.loads(line) for line in PLAN.read_text(encoding="utf-8").splitlines()
    ]
    result, plan = preflight.build(ROOT, CONFIG)
    assert stored_result == result
    assert stored_plan == plan
