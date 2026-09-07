from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from jbspan.evaluator_panel_redesign import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_evaluator_panel_wildguard_cumulative_sentinel_e0f1b as cumulative  # noqa: E402

CONTRACT_PATH = (
    ROOT / "configs/evaluator_panel/calibration_redesign_e0f1b_cumulative_sentinel_v1.json"
)


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_e0f1b_selection_seed_is_identity_derived() -> None:
    seed = cumulative.derived_selection_seed(
        micro_result_identity=("bd301ad9d150cd71362f89ee67dfdaec1007233c0f08af2ddd3361d5ebcf7c40"),
        interruption_result_identity=(
            "79ddd4d45f6ac0f4eb2a82ed6595123b5188a8d337e703751b56188f56d0acea"
        ),
    )
    assert seed == "70fef633c9f6322473f299495d33bbbda99c698ef2e04780b21d66df3da516aa"


def test_e0f1b_v1_called_identities_are_mapped_without_private_content() -> None:
    contract, base_contract, _, _ = cumulative.validate_contract(ROOT, CONTRACT_PATH)
    base_plan, existing, _ = cumulative.base.build_plan(ROOT, base_contract)
    rows = cumulative.derive_v1_called_identity_rows_without_opening_private(
        ROOT,
        contract,
        base_contract,
        base_plan,
    )
    assert len(rows) == 14
    assert len({row["record_id"] for row in rows}) == 14
    assert all(row["private_record_content_opened"] is False for row in rows)
    assert all(row["human_label_written"] is False for row in rows)

    existing_by_id = {record.record_id: record for record in existing}
    counts = Counter(
        (
            existing_by_id[str(row["record_id"])].source_id,
            existing_by_id[str(row["record_id"])].human_label,
        )
        for row in rows
    )
    assert counts == Counter(
        {
            ("harmbench", "HARMFUL"): 7,
            ("harmbench", "SAFE"): 7,
        }
    )


def test_e0f1b_additions_are_balanced_disjoint_and_round_interleaved() -> None:
    (
        _,
        base_contract,
        adopted_rows,
        plan,
        exclusion_rows,
        identity_rows,
        selection_summary,
        plan_summary,
    ) = cumulative.prepare_design(ROOT, CONTRACT_PATH)
    assert len(adopted_rows) == 72
    assert len(plan) == 72
    assert len(identity_rows) == 72
    assert plan_summary["source_input_truncation_count"] == 0
    assert selection_summary["cumulative_unique_behavior_groups"] == 107

    adopted_ids = {str(row["record_id"]) for row in adopted_rows}
    excluded_ids = {str(row["record_id"]) for row in exclusion_rows}
    addition_ids = {str(row["record_id"]) for row in identity_rows}
    assert len(adopted_ids | addition_ids) == 144
    assert not (adopted_ids & addition_ids)
    assert not (excluded_ids & addition_ids)

    existing = cumulative.base.load_existing_records(ROOT, base_contract)
    existing_by_id = {record.record_id: record for record in existing}
    counts = Counter(
        (
            existing_by_id[str(row["record_id"])].source_id,
            existing_by_id[str(row["record_id"])].human_label,
        )
        for row in identity_rows
    )
    assert counts == Counter(
        {(source, label): 12 for source in cumulative.SOURCES for label in cumulative.LABELS}
    )
    for round_index in range(1, 13):
        round_rows = [row for row in identity_rows if row["execution_round"] == round_index]
        assert len(round_rows) == 6
        round_cells = {
            (
                existing_by_id[str(row["record_id"])].source_id,
                existing_by_id[str(row["record_id"])].human_label,
            )
            for row in round_rows
        }
        assert round_cells == {
            (source, label) for source in cumulative.SOURCES for label in cumulative.LABELS
        }


def test_completed_e0f1b_preflight_identity_and_seals() -> None:
    path = ROOT / "data/evaluator_panel_v2/e0f1b_cumulative_preflight.safe.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    identity = result.pop("result_identity_sha256")
    assert hashlib.sha256(canonical_json_bytes(result)).hexdigest() == identity
    assert result["new_model_inference_performed"] is False
    assert result["automatic_execution_started"] is False
    assert result["explicit_post_preflight_authorization_required"] is True
    assert result["v1_private_record_contents_opened"] is False
    assert result["v1_wildguard_labels_or_candidate_metrics_used"] is False
    assert result["addition_selection_used_wildguard_or_existing_signal_predictions"] is False
    assert result["heldout_opened"] is False
    assert result["p3_opened"] is False
    assert result["topology_opened"] is False


def test_e0f1b_run_refuses_execution_without_review_confirmation() -> None:
    outputs = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["outputs"]
    terminal_paths = [
        ROOT / outputs[name]
        for name in (
            "addition_axis_path",
            "cumulative_axis_path",
            "execution_path",
            "result_path",
        )
    ]
    assert not any(path.exists() for path in terminal_paths)
    with pytest.raises(PermissionError, match="confirm-reviewed-frozen-preflight"):
        cumulative.run(ROOT, CONTRACT_PATH, confirmed=False)
    assert not any(path.exists() for path in terminal_paths)


def test_completed_e0f1b_result_identity_and_seals_when_present() -> None:
    path = ROOT / "data/evaluator_panel_v2/e0f1b_cumulative_result.safe.json"
    if not path.is_file():
        return
    result = json.loads(path.read_text(encoding="utf-8"))
    identity = result.pop("result_identity_sha256")
    assert hashlib.sha256(canonical_json_bytes(result)).hexdigest() == identity
    assert result["new_scientific_completion_call_ceiling"] == 72
    assert result["cumulative_scientific_records"] == 144
    assert result["cumulative_result_is_independent_confirmation"] is False
    assert result["v1_private_record_contents_opened"] is False
    assert result["heldout_opened"] is False
    assert result["p3_opened"] is False
    assert result["topology_opened"] is False
    assert result["panel_qualified"] is False
